import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
import pytz

# Initial debug output
print("\n" + "=" * 80)
print("V20 SCANNER SCRIPT STARTING")
print("=" * 80)
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Files in current directory: {os.listdir('.')}")
print(f"stocks.xlsx exists? {os.path.exists('stocks.xlsx')}")
print("=" * 80 + "\n")

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
            import traceback
            traceback.print_exc()
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
            
            print(f"✅ Email sent successfully with {len(self.alerts)} alerts!")
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            import traceback
            traceback.print_exc()
    
    def run_scan(self):
        """Main scanning function"""
        print("\n" + "=" * 80)
        print("RUN_SCAN FUNCTION CALLED")
        print("=" * 80)
        print(f"Starting V20 scan at {datetime.now()}")
        print("=" * 80 + "\n")
        
        # Check if it's weekend - TEMPORARILY DISABLED FOR TESTING
        # ist = pytz.timezone('Asia/Kolkata')
        # now_ist = datetime.now(ist)
        # if now_ist.weekday() >= 5:
        #     print("Weekend - No scan performed")
        #     return
        
        print("Reading Excel file...")
        stocks = self.read_stocks_from_excel()
        
        print(f"\n{'='*60}")
        print(f"EXCEL FILE READ SUCCESSFULLY")
        print(f"Total groups found: {len(stocks)}")
        for group, symbols in stocks.items():
            print(f"  {group}: {len(symbols)} stocks")
            print(f"  Symbols: {symbols[:3]}..." if len(symbols) > 3 else f"  Symbols: {symbols}")
        print(f"{'='*60}\n")
        
        if not stocks or all(len(v) == 0 for v in stocks.values()):
            print("ERROR: No stocks found in Excel file!")
            print("Please check:")
            print("  1. Excel file name is 'stocks.xlsx'")
            print("  2. Sheet names are: v40, v40next, v200")
            print("  3. Stock symbols are in Column B")
            return
        
        total_patterns_found = 0
        
        for group, symbols in stocks.items():
            print(f"\n{'='*60}")
            print(f"Scanning {group} group ({len(symbols)} stocks)...")
            print(f"{'='*60}")
            
            for symbol in symbols:
                try:
                    print(f"\n  Analyzing {symbol}...")
                    
                    patterns = self.find_20_percent_patterns(symbol)
                    
                    if patterns:
                        print(f"    ✓ Found {len(patterns)} pattern(s) with 20%+ gain")
                        for idx, p in enumerate(patterns, 1):
                            print(f"      Pattern {idx}: Start={p['start_date']}, Price=Rs.{p['start_price']}, Gain={p['gain_percent']}%")
                        total_patterns_found += len(patterns)
                        
                        current_price, sma_200 = self.get_current_price_and_sma(symbol)
                        print(f"    Current Price: Rs.{current_price}")
                        
                        if group == 'v200' and sma_200:
                            price_vs_sma = "BELOW" if current_price < sma_200 else "ABOVE"
                            print(f"    200 SMA: Rs.{sma_200} (Price is {price_vs_sma} SMA)")
                        
                        alerts_before = len(self.alerts)
                        self.check_alerts(symbol, group, patterns, current_price, sma_200)
                        alerts_after = len(self.alerts)
                        
                        if alerts_after > alerts_before:
                            print(f"    🔔 ALERT GENERATED!")
                        else:
                            print(f"    ℹ️  Pattern found but doesn't meet alert conditions")
                            print(f"       (Current price not within 5% below any pattern start)")
                    else:
                        print(f"    - No 20% patterns found in last year")
                    
                except Exception as e:
                    print(f"  ❌ Error processing {symbol}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        print(f"\n{'='*80}")
        print(f"SCAN SUMMARY")
        print(f"{'='*80}")
        print(f"Total 20% patterns found: {total_patterns_found}")
        print(f"Total alerts generated: {len(self.alerts)}")
        print(f"{'='*80}\n")
        
        if self.alerts:
            print("📧 Attempting to send email...")
            print(f"From: {self.email_from}")
            print(f"To: {self.email_to}")
            print(f"Number of alerts: {len(self.alerts)}\n")
            self.send_email()
        else:
            print("\n⚠️  No alerts generated today.")
            print("\nREASON: Patterns were found but current prices don't meet alert conditions:")
            print("  - NEAR ALERT: Current price must be within 5% BELOW pattern start price")
            print("  - ACTIVATED ALERT: Current price must match pattern start (within 1%)")
            print("  - v200 CONDITION: Price must also be BELOW 200 SMA")
            print("\nThis is normal - it means no buying opportunities right now.")
        
        print("\n" + "=" * 80)
        print("SCAN COMPLETED SUCCESSFULLY")
        print("=" * 80)

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("MAIN EXECUTION STARTING")
    print("=" * 80)
    
    # Configuration
    EXCEL_FILE = "stocks.xlsx"
    EMAIL_TO = "deb.4uuu@gmail.com"
    EMAIL_FROM = os.environ.get('EMAIL_FROM')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
    
    print(f"Excel File: {EXCEL_FILE}")
    print(f"Email To: {EMAIL_TO}")
    print(f"Email From: {EMAIL_FROM}")
    print(f"Email Password: {'*' * len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 'NOT SET'}")
    print("=" * 80 + "\n")
    
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("ERROR: Email credentials not set!")
        print("EMAIL_FROM:", EMAIL_FROM)
        print("EMAIL_PASSWORD:", "SET" if EMAIL_PASSWORD else "NOT SET")
        sys.exit(1)
    
    # Run scanner
    print("Creating V20Scanner instance...")
    scanner = V20Scanner(EXCEL_FILE, EMAIL_TO, EMAIL_FROM, EMAIL_PASSWORD)
    
    print("Calling run_scan()...")
    scanner.run_scan()
    
    print("\n" + "=" * 80)
    print("SCRIPT EXECUTION COMPLETED")
    print("=" * 80)
