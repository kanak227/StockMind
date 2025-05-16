from apscheduler.schedulers.background import BackgroundScheduler
from .alert_manager import check_price_alert, check_rsi_alert

alerts = []  # This should be replaced with DB storage in production

def check_alerts():
    for alert in alerts:
        if alert['type'] == 'price':
            triggered = check_price_alert(alert['ticker'], alert['target'], alert['direction'])
        elif alert['type'] == 'rsi':
            triggered = check_rsi_alert(alert['ticker'], alert['threshold'], alert['direction'])
        else:
            triggered = False

        if triggered:
            print(f"[ALERT TRIGGERED] {alert}")
            # TODO: Send notification (email, SMS, etc.)

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_alerts, 'interval', minutes=2)
    scheduler.start()
