import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import pytz

class V20Scanner:
    def __init__(self, excel_file_path, email_to, email_from, email_password):
        self.excel_file_path = excel_file_path
        self.email_to = email_to
        self.email_from = email_from
        self.email_password = email_password
        self.alerts = []
        
    def read_stocks_from_excel(self):
        """Read stock symbols from Excel file"""
        try:
            xls = pd.ExcelFile(self.excel_file_path)
            stocks = {}
            for sheet_name in ['v40', 'v40next', 'v200']:
                if sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    stocks[sheet_name] = df.iloc[:, 1].dropna().tolist()
            return stocks
        except Exception as e:
            print(f"Error reading Excel file: {e}")
            return {}
    
    def find_20_percent_patterns(self, symbol, days=365):
        """Find consecutive green candle patterns with 20%+ gain"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            stock = yf.Ticker(symbol)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                return []
            
            patterns = []
            i = 0
            
            while i < len(df):
                start_idx = i
                start_price = df.iloc[i]['Open']
                current_high = df.iloc[i]['Close']
                
                j = i
                consecutive_green = 0
                
                while j < len(df) and df.iloc[j]['Close'] > df.iloc[j]['Open']:
                    current_high = max(current_high, df.iloc[j]['Close'])
                    consecutive_green += 1
                    j += 1
                
                if consecutive_green > 0:
                    gain_percent = ((current_high - start_price) / start_price) * 100
                    
                    if gain_percent >= 20:
                        patterns.append({
                            'start_date': df.index[start_idx].strftime('%Y-%m-%d'),
                            'start_price': round(start_price, 2),
                            'end_price': round(current_high, 2),
                            'gain_percent': round(gain_percent, 2),
                            'candles': consecutive_green
                        })
                
                i = j if j > i else i + 1
            
            return patterns
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            return []
    
    def get_current_price_and_sma(self, symbol):
        """Get current price and 200 SMA"""
        try:
            stock = yf.Ticker(symbol)
            df = stock.history(period='220d')
            
            if df.empty:
                return None, None
            
            current_price = df.iloc[-1]['Close']
            sma_200 = df['Close'].rolling(window=200).mean().iloc[-1] if len(df) >= 200 else None
            
            return round(current_price, 2), round(sma_200, 2) if sma_200 else None
        except Exception as e:
            print(f"Error getting current price for {symbol}: {e}")
            return None, None
    
    def check_alerts(self, symbol, group, patterns, current_price, sma_200=None):
        """Check if stock meets alert conditions"""
        if not patterns or current_price is None:
            return
        
        if group == 'v200':
            if sma_200 is None or current_price >= sma_200:
                return
        
        for pattern in patterns:
            start_price = pattern['start_price']
            difference_percent = abs((current_price - start_price) / start_price) * 100
            
            if difference_percent <= 1:
                alert_msg = f"V20 ACTIVATED - {symbol} ({group})\n"
                alert_msg += f"   Current Price: Rs.{current_price}\n"
                alert_msg += f"   Pattern Start: Rs.{start_price} (Date: {pattern['start_date']})\n"
                alert_msg += f"   Pattern Gain: {pattern['gain_percent']}%\n"
                if group == 'v200' and sma_200:
                    alert_msg += f"   200 SMA: Rs.{sma_200}\n"
                self.alerts.append(alert_msg)
            
            elif difference_percent <= 5 and current_price < start_price:
                alert_msg = f"NEAR V20 - {symbol} ({group})\n"
                alert_msg += f"   Current Price: Rs.{current_price}\n"
                alert_msg += f"   Pattern Start: Rs.{start_price} (Date: {pattern['start_date']})\n"
                alert_msg += f"   Difference: {round(difference_percent, 2)}%\n"
                alert_msg += f"   Pattern Gain: {pattern['gain_percent']}%\n"
                if group == 'v200' and sma_200:
                    alert_msg += f"   200 SMA: Rs.{sma_200}\n"
                self.alerts.append(alert_msg)
    
    def send_email(self):
        """Send consolidated email with all alerts"""
        if not self.alerts:
            print("No alerts to send.")
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = f"V20 Scanner Alerts - {datetime.now().strftime('%Y-%m-%d')}"
            
            body = "V20 SCANNER DAILY REPORT\n"
            body += "=" * 50 + "\n\n"
            body += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M IST')}\n"
            body += f"Total Alerts: {len(self.alerts)}\n\n"
            body += "=" * 50 + "\n\n"
            body += "\n".join(self.alerts)
            body += "\n\n" + "=" * 50 + "\n"
            body += "Note: V20 pattern = 20%+ gain from consecutive green candles\n"
            body += "NEAR = Current price within 5% of pattern start\n"
            body += "ACTIVATED = Current price matches pattern start\n"
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.email_from, self.email_password)
            server.send_message(msg)
            server.quit()
            
            print(f"Email sent successfully with {len(self.alerts)} alerts!")
        except Exception as e:
            print(f"Error sending email: {e}")
    
    def run_scan(self):
        """Main scanning function"""
        print(f"Starting V20 scan at {datetime.now()}")
        
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)
        if now_ist.weekday() >= 5:
            print("Weekend - No scan performed")
            return
        
        stocks = self.read_stocks_from_excel()
        
        for group, symbols in stocks.items():
            print(f"\nScanning {group} group ({len(symbols)} stocks)...")
            
            for symbol in symbols:
                try:
                    print(f"  Analyzing {symbol}...")
                    
                    patterns = self.find_20_percent_patterns(symbol)
                    
                    if patterns:
                        current_price, sma_200 = self.get_current_price_and_sma(symbol)
                        self.check_alerts(symbol, group, patterns, current_price, sma_200)
                    
                except Exception as e:
                    print(f"  Error processing {symbol}: {e}")
                    continue
        
        if self.alerts:
            self.send_email()
        else:
            print("\nNo alerts found today.")

if __name__ == "__main__":
    EXCEL_FILE = "stocks.xlsx"
    EMAIL_TO = "deb.4uuu@gmail.com"
    EMAIL_FROM = os.environ.get('EMAIL_FROM')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
    
    scanner = V20Scanner(EXCEL_FILE, EMAIL_TO, EMAIL_FROM, EMAIL_PASSWORD)
    scanner.run_scan()
