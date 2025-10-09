# src/ib_quant_kit/error_handler.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from rich.console import Console

console = Console()

@dataclass
class ErrorRecord:
    timestamp: datetime
    code: int
    req_id: int
    message: str
    symbol: Optional[str] = None
    severity: str = "ERROR"

class ErrorHandler:
    """Centralized error handling with alerting thresholds"""
    
    # IBKR error code mappings
    CONNECTIVITY_ERRORS = {1100, 1101, 1102, 2103, 2104, 2105, 2106, 2108}
    ORDER_ERRORS = {201, 202, 203, 399, 400, 401, 404, 10147, 10148}
    MARKET_DATA_ERRORS = {162, 200, 354}
    CRITICAL_ERRORS = {502, 504, 507, 1102}
    
    def __init__(self, max_errors_per_hour=50):
        self.errors = []
        self.max_errors_per_hour = max_errors_per_hour
        self._consecutive_connection_errors = 0
    
    def handle(self, req_id: int, error_code: int, error_string: str, symbol: Optional[str] = None):
        """Process error and determine severity"""
        
        # Classify error
        if error_code in self.CONNECTIVITY_ERRORS:
            severity = "CRITICAL" if error_code in self.CRITICAL_ERRORS else "WARNING"
            self._handle_connectivity_error(error_code, error_string)
        elif error_code in self.ORDER_ERRORS:
            severity = "ERROR"
            self._handle_order_error(req_id, error_code, error_string, symbol)
        elif error_code in self.MARKET_DATA_ERRORS:
            severity = "WARNING"
            self._handle_market_data_error(req_id, error_code, error_string)
        else:
            severity = "INFO"
        
        # Record error
        rec = ErrorRecord(
            timestamp=datetime.utcnow(),
            code=error_code,
            req_id=req_id,
            message=error_string,
            symbol=symbol,
            severity=severity
        )
        self.errors.append(rec)
        
        # Check alert thresholds
        self._check_alert_conditions()
        
        return severity
    
    def _handle_connectivity_error(self, code: int, message: str):
        """Handle connection issues"""
        self._consecutive_connection_errors += 1
        
        if code == 1100:  # Connectivity lost
            console.log(f"[bold red]CONNECTION LOST[/]: {message}")
            console.log("[yellow]Orders may be at risk - manual check recommended[/]")
        elif code == 1101:  # Connectivity restored (data lost)
            console.log(f"[bold yellow]CONNECTION RESTORED[/]: {message}")
            console.log("[yellow]Market data may have gaps[/]")
            self._consecutive_connection_errors = 0
        elif code == 1102:  # Connectivity restored (data maintained)
            console.log(f"[bold green]CONNECTION RESTORED[/]: {message}")
            self._consecutive_connection_errors = 0
        elif code == 2103:  # Market data farm disconnected
            console.log(f"[yellow]Market data delayed[/]: {message}")
        
        # Alert if many consecutive connection errors
        if self._consecutive_connection_errors > 5:
            self._send_alert("CRITICAL", "5+ consecutive connection errors - manual intervention needed")
    
    def _handle_order_error(self, req_id: int, code: int, message: str, symbol: Optional[str]):
        """Handle order-related errors"""
        sym_str = f" ({symbol})" if symbol else ""
        
        if code == 201:  # Order rejected
            console.log(f"[bold red]ORDER REJECTED[/]{sym_str}: {message}")
        elif code == 202:  # Order cancelled
            console.log(f"[yellow]ORDER CANCELLED[/]{sym_str}: {message}")
        elif code in {399, 400, 401}:  # Order message errors
            console.log(f"[red]ORDER ERROR[/]{sym_str}: {message}")
        elif code == 10147:  # Order ID already in use
            console.log(f"[red]DUPLICATE ORDER ID[/]{sym_str}: {message}")
        else:
            console.log(f"[red]ORDER ERROR {code}[/]{sym_str}: {message}")
    
    def _handle_market_data_error(self, req_id: int, code: int, message: str):
        """Handle market data errors"""
        if code == 162:  # Historical data farm issue
            console.log(f"[yellow]Historical data unavailable[/]: reqId={req_id}")
        elif code == 200:  # No security definition
            console.log(f"[yellow]Invalid symbol[/]: reqId={req_id} - {message}")
        elif code == 354:  # Subscription not available
            console.log(f"[yellow]Market data not available[/]: reqId={req_id}")
    
    def _check_alert_conditions(self):
        """Check if error rate exceeds thresholds"""
        from datetime import timedelta
        
        now = datetime.utcnow()
        last_hour = now - timedelta(hours=1)
        
        # Count errors in last hour
        recent = [e for e in self.errors if e.timestamp > last_hour]
        
        if len(recent) > self.max_errors_per_hour:
            self._send_alert(
                "WARNING",
                f"{len(recent)} errors in last hour (threshold: {self.max_errors_per_hour})"
            )
    
    def _send_alert(self, level: str, message: str):
        """Send alert via configured channels"""
        console.log(f"[bold red]ALERT[/] [{level}]: {message}")
        
        # Hook to Slack/email if configured
        try:
            from .alerts.slack_alerts import send_slack
            send_slack(f"[{level}] {message}")
        except Exception:
            pass
    
    def get_recent_errors(self, hours: int = 1):
        """Get errors from last N hours"""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [e for e in self.errors if e.timestamp > cutoff]
    
    def reset(self):
        """Clear error history"""
        self.errors.clear()
        self._consecutive_connection_errors = 0

# Global instance
error_handler = ErrorHandler()
