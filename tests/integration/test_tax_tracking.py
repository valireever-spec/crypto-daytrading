"""Integration tests for tax tracking system."""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.analytics.tax_calculator import (
    TaxCalculator,
    Jurisdiction,
    Trade,
    TaxStatus,
    init_tax_calculator,
    get_tax_calculator,
)


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def tax_calc():
    """Initialize tax calculator for testing."""
    calc = TaxCalculator(jurisdiction=Jurisdiction.GERMANY)
    return calc


class TestTaxCalculatorCore:
    """Test core tax calculation logic."""

    def test_add_single_trade(self, tax_calc):
        """Test adding a single trade."""
        trade = Trade(
            trade_id="001",
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.5,
            price=50000,
            timestamp=datetime.utcnow(),
            fees=25.0,
        )
        tax_calc.add_trade(trade)
        assert len(tax_calc.trades) == 1
        assert tax_calc.trades[0].symbol == "BTCUSDT"

    def test_fifo_matching(self, tax_calc):
        """Test FIFO trade matching."""
        buy1 = Trade(
            trade_id="buy1",
            symbol="BTCUSDT",
            side="BUY",
            quantity=1.0,
            price=50000,
            timestamp=datetime(2024, 1, 1),
            fees=50,
        )
        buy2 = Trade(
            trade_id="buy2",
            symbol="BTCUSDT",
            side="BUY",
            quantity=1.0,
            price=55000,
            timestamp=datetime(2024, 2, 1),
            fees=55,
        )
        sell1 = Trade(
            trade_id="sell1",
            symbol="BTCUSDT",
            side="SELL",
            quantity=1.5,
            price=60000,
            timestamp=datetime(2024, 3, 1),
            fees=90,
        )

        tax_calc.add_trade(buy1)
        tax_calc.add_trade(buy2)
        tax_calc.add_trade(sell1)

        events = tax_calc.match_trades_fifo()

        # Should create 2 taxable events
        assert len(events) == 2
        assert events[0].quantity == 1.0  # First buy matched
        assert events[1].quantity == 0.5  # Partial second buy matched

    def test_holding_period_classification(self, tax_calc):
        """Test holding period tax status."""
        # Long-term hold (>365 days)
        buy = Trade(
            trade_id="buy",
            symbol="ETHUSDT",
            side="BUY",
            quantity=10,
            price=2000,
            timestamp=datetime(2023, 1, 1),
        )
        sell_long = Trade(
            trade_id="sell_long",
            symbol="ETHUSDT",
            side="SELL",
            quantity=10,
            price=2500,
            timestamp=datetime(2024, 1, 2),
        )
        sell_short = Trade(
            trade_id="sell_short",
            symbol="ETHUSDT",
            side="SELL",
            quantity=10,
            price=2500,
            timestamp=datetime(2023, 6, 1),
        )

        tax_calc.add_trade(buy)
        tax_calc.add_trade(sell_long)
        events = tax_calc.match_trades_fifo()
        assert events[0].tax_status == TaxStatus.LONG_TERM
        assert events[0].holding_period_days >= 365

        # Reset and test short-term
        tax_calc = TaxCalculator(jurisdiction=Jurisdiction.GERMANY)
        tax_calc.add_trade(buy)
        tax_calc.add_trade(sell_short)
        events = tax_calc.match_trades_fifo()
        assert events[0].tax_status == TaxStatus.SHORT_TERM
        assert events[0].holding_period_days < 365

    def test_deductible_expenses(self, tax_calc):
        """Test deductible expense tracking."""
        tax_calc.add_deductible_expense("binance_fees", 100.50)
        tax_calc.add_deductible_expense("software", 50.00)
        tax_calc.add_deductible_expense("binance_fees", 25.50)

        assert len(tax_calc.deductible_expenses) == 2
        assert tax_calc.deductible_expenses["binance_fees"] == 126.0
        assert tax_calc.deductible_expenses["software"] == 50.0

    def test_germany_long_term_tax_free(self, tax_calc):
        """Test Germany's 1-year tax-free rule."""
        buy = Trade(
            trade_id="buy",
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.1,
            price=50000,
            timestamp=datetime(2023, 1, 1),
            fees=50,
        )
        sell = Trade(
            trade_id="sell",
            symbol="BTCUSDT",
            side="SELL",
            quantity=0.1,
            price=60000,
            timestamp=datetime(2024, 1, 2),
            fees=60,
        )

        tax_calc.add_trade(buy)
        tax_calc.add_trade(sell)

        liability = tax_calc.calculate_liability()

        # Long-term gain in Germany should have 0% tax
        assert liability.long_term_gains > 0
        assert liability.short_term_gains == 0
        assert liability.estimated_tax == 0

    def test_germany_short_term_42_percent(self, tax_calc):
        """Test Germany's 42% short-term tax."""
        buy = Trade(
            trade_id="buy",
            symbol="ETHUSDT",
            side="BUY",
            quantity=10,
            price=2000,
            timestamp=datetime(2024, 1, 1),
        )
        sell = Trade(
            trade_id="sell",
            symbol="ETHUSDT",
            side="SELL",
            quantity=10,
            price=2500,
            timestamp=datetime(2024, 6, 1),  # < 1 year
        )

        tax_calc.add_trade(buy)
        tax_calc.add_trade(sell)

        liability = tax_calc.calculate_liability()

        # Short-term gain should be taxed at 42% + 5.5% solidarity
        gain = 10 * (2500 - 2000)  # €5,000
        expected_tax = gain * 0.42 * (1 + 0.055)  # 42% + 5.5% solidarity
        assert abs(liability.estimated_tax - expected_tax) < 10

    def test_tax_report_generation(self, tax_calc):
        """Test comprehensive tax report generation."""
        buy = Trade(
            trade_id="buy",
            symbol="BNBUSDT",
            side="BUY",
            quantity=5,
            price=300,
            timestamp=datetime(2024, 1, 1),
            fees=15,
        )
        sell = Trade(
            trade_id="sell",
            symbol="BNBUSDT",
            side="SELL",
            quantity=5,
            price=400,
            timestamp=datetime(2024, 3, 1),
            fees=20,
        )

        tax_calc.add_trade(buy)
        tax_calc.add_trade(sell)
        tax_calc.add_deductible_expense("trading_fees", 10)

        report = tax_calc.generate_report()

        assert "jurisdiction" in report
        assert "summary" in report
        assert "tax_events" in report
        assert "deductible_expenses" in report
        assert "recommendations" in report
        assert len(report["tax_events"]) > 0

    def test_usa_jurisdiction(self):
        """Test USA tax calculation."""
        calc = TaxCalculator(jurisdiction=Jurisdiction.USA)

        buy = Trade(
            trade_id="buy",
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.5,
            price=50000,
            timestamp=datetime(2024, 1, 1),
        )
        sell_short = Trade(
            trade_id="sell_short",
            symbol="BTCUSDT",
            side="SELL",
            quantity=0.5,
            price=60000,
            timestamp=datetime(2024, 2, 1),
        )

        calc.add_trade(buy)
        calc.add_trade(sell_short)

        liability = calc.calculate_liability()

        # USA short-term capital gains are taxed as ordinary income (37% top bracket)
        assert liability.jurisdiction == Jurisdiction.USA
        assert liability.estimated_tax > 0

    def test_uk_annual_exemption(self):
        """Test UK's £3,000 annual exemption."""
        calc = TaxCalculator(jurisdiction=Jurisdiction.UK)

        buy = Trade(
            trade_id="buy",
            symbol="ETHUSDT",
            side="BUY",
            quantity=5,
            price=2000,
            timestamp=datetime(2024, 1, 1),
        )
        sell = Trade(
            trade_id="sell",
            symbol="ETHUSDT",
            side="SELL",
            quantity=5,
            price=2600,  # £3,000 gain
            timestamp=datetime(2024, 3, 1),
        )

        calc.add_trade(buy)
        calc.add_trade(sell)

        liability = calc.calculate_liability()

        # Gain is exactly £3,000, which should be tax-free due to exemption
        assert liability.estimated_tax == 0


class TestTaxAPIEndpoints:
    """Test tax tracking API endpoints."""

    def test_initialize_endpoint(self, client):
        """Test tax tracker initialization endpoint."""
        response = client.post("/api/tax/initialize?jurisdiction=DE")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "initialized"
        assert data["jurisdiction"] == "DE"

    def test_add_trade_endpoint(self, client):
        """Test adding a trade via API."""
        # Initialize first
        client.post("/api/tax/initialize?jurisdiction=DE")

        response = client.post(
            "/api/tax/add-trade",
            json={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.5,
                "price": 50000,
                "timestamp": "2024-01-01T00:00:00",
                "fees": 25,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "added"
        assert data["symbol"] == "BTCUSDT"
        assert data["side"] == "BUY"

    def test_add_expense_endpoint(self, client):
        """Test adding deductible expense."""
        client.post("/api/tax/initialize?jurisdiction=DE")

        response = client.post(
            "/api/tax/add-expense",
            json={
                "category": "trading_fees",
                "amount": 100.50,
                "description": "Binance trading fees",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "added"
        assert data["category"] == "trading_fees"

    def test_get_liability_endpoint(self, client):
        """Test getting tax liability."""
        # Initialize and add trades
        client.post("/api/tax/initialize?jurisdiction=DE")
        client.post(
            "/api/tax/add-trade",
            json={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.5,
                "price": 50000,
                "timestamp": "2024-01-01T00:00:00",
            },
        )
        client.post(
            "/api/tax/add-trade",
            json={
                "symbol": "BTCUSDT",
                "side": "SELL",
                "quantity": 0.5,
                "price": 60000,
                "timestamp": "2024-06-01T00:00:00",
            },
        )

        response = client.get("/api/tax/liability")
        assert response.status_code == 200
        data = response.json()
        assert "estimated_tax" in data
        assert "effective_tax_rate_pct" in data
        assert data["net_gain_loss"] > 0

    def test_get_report_endpoint(self, client):
        """Test getting full tax report."""
        client.post("/api/tax/initialize?jurisdiction=DE")

        response = client.get("/api/tax/report")
        assert response.status_code == 200
        data = response.json()
        assert data["jurisdiction"] == "DE"
        assert "summary" in data
        assert "tax_events" in data
        assert "recommendations" in data

    def test_export_json_endpoint(self, client):
        """Test exporting data as JSON."""
        client.post("/api/tax/initialize?jurisdiction=DE")

        response = client.get("/api/tax/export/json")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "exported"
        assert data["format"] == "json"

    def test_export_csv_endpoint(self, client):
        """Test exporting data as CSV."""
        client.post("/api/tax/initialize?jurisdiction=DE")

        response = client.get("/api/tax/export/csv")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "exported"
        assert data["format"] == "csv"

    def test_get_summary_endpoint(self, client):
        """Test getting quick tax summary."""
        client.post("/api/tax/initialize?jurisdiction=DE")

        response = client.get("/api/tax/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["jurisdiction"] == "DE"
        assert "estimated_tax" in data
        assert "net_after_tax" in data
        assert "jurisdiction_tip" in data

    def test_invalid_jurisdiction(self, client):
        """Test error handling for invalid jurisdiction."""
        response = client.post("/api/tax/initialize?jurisdiction=XX")
        assert response.status_code == 400


class TestTaxIntegration:
    """Integration tests with paper trading."""

    def test_sync_from_paper_trading(self, client):
        """Test syncing trades from paper trading engine."""
        # Initialize tax tracker
        client.post("/api/tax/initialize?jurisdiction=DE")

        # Place some paper trades
        client.post(
            "/api/paper/order",
            params={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.1,
                "current_price": 50000,
            },
        )

        # Sync from paper trading
        response = client.get("/api/tax/sync-from-paper-trading")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "synced"
        assert data["trades_synced"] >= 0  # May be 0 or more depending on state

    def test_complete_workflow(self, client):
        """Test complete tax tracking workflow."""
        # 1. Initialize
        resp = client.post("/api/tax/initialize?jurisdiction=DE")
        assert resp.status_code == 200

        # 2. Add trades
        trades = [
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.5,
                "price": 50000,
                "timestamp": "2024-01-01T00:00:00",
                "fees": 25,
            },
            {
                "symbol": "ETHUSDT",
                "side": "BUY",
                "quantity": 5,
                "price": 2000,
                "timestamp": "2024-01-15T00:00:00",
                "fees": 50,
            },
            {
                "symbol": "BTCUSDT",
                "side": "SELL",
                "quantity": 0.5,
                "price": 65000,
                "timestamp": "2024-06-01T00:00:00",
                "fees": 32,
            },
            {
                "symbol": "ETHUSDT",
                "side": "SELL",
                "quantity": 5,
                "price": 3000,
                "timestamp": "2024-07-01T00:00:00",
                "fees": 75,
            },
        ]

        for trade in trades:
            resp = client.post("/api/tax/add-trade", json=trade)
            assert resp.status_code == 200

        # 3. Add deductible expenses
        expenses = [
            {"category": "trading_fees", "amount": 100, "description": "Monthly fees"},
            {"category": "software", "amount": 50, "description": "Trading software"},
        ]

        for expense in expenses:
            resp = client.post("/api/tax/add-expense", json=expense)
            assert resp.status_code == 200

        # 4. Get liability
        resp = client.get("/api/tax/liability")
        assert resp.status_code == 200
        liability = resp.json()
        assert liability["estimated_tax"] > 0

        # 5. Get full report
        resp = client.get("/api/tax/report")
        assert resp.status_code == 200
        report = resp.json()
        assert len(report["tax_events"]) == 2  # 2 sell events

        # 6. Get summary
        resp = client.get("/api/tax/summary")
        assert resp.status_code == 200
        summary = resp.json()
        assert summary["net_position"] > 0
        assert summary["net_after_tax"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
