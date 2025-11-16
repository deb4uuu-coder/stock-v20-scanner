def run_scan(self):
        """Main scanning function"""
        print(f"Starting V20 scan at {datetime.now()}")
        
        # Check if it's weekend - TEMPORARILY DISABLED FOR TESTING
        # ist = pytz.timezone('Asia/Kolkata')
        # now_ist = datetime.now(ist)
        # if now_ist.weekday() >= 5:  # Saturday=5, Sunday=6
        #     print("Weekend - No scan performed")
        #     return
        
        stocks = self.read_stocks_from_excel()
        
        print(f"\n{'='*60}")
        print(f"EXCEL FILE READ SUCCESSFULLY")
        print(f"Total groups found: {len(stocks)}")
        for group, symbols in stocks.items():
            print(f"  {group}: {len(symbols)} stocks")
        print(f"{'='*60}\n")
        
        total_patterns_found = 0
        
        for group, symbols in stocks.items():
            print(f"\nScanning {group} group ({len(symbols)} stocks)...")
            
            for symbol in symbols:
                try:
                    print(f"  Analyzing {symbol}...")
                    
                    patterns = self.find_20_percent_patterns(symbol)
                    
                    if patterns:
                        print(f"    ✓ Found {len(patterns)} pattern(s) with 20%+ gain")
                        total_patterns_found += len(patterns)
                        
                        current_price, sma_200 = self.get_current_price_and_sma(symbol)
                        print(f"    Current Price: Rs.{current_price}")
                        
                        if group == 'v200' and sma_200:
                            print(f"    200 SMA: Rs.{sma_200} (Price {'<' if current_price < sma_200 else '>='} SMA)")
                        
                        # Check for alerts
                        alerts_before = len(self.alerts)
                        self.check_alerts(symbol, group, patterns, current_price, sma_200)
                        alerts_after = len(self.alerts)
                        
                        if alerts_after > alerts_before:
                            print(f"    🔔 ALERT GENERATED!")
                        else:
                            print(f"    ℹ️  Pattern found but doesn't meet alert conditions")
                    else:
                        print(f"    - No 20% patterns found")
                    
                except Exception as e:
                    print(f"  ❌ Error processing {symbol}: {e}")
                    continue
        
        print(f"\n{'='*60}")
        print(f"SCAN SUMMARY")
        print(f"{'='*60}")
        print(f"Total 20% patterns found: {total_patterns_found}")
        print(f"Total alerts generated: {len(self.alerts)}")
        print(f"{'='*60}\n")
        
        if self.alerts:
            print("📧 Attempting to send email...")
            print(f"From: {self.email_from}")
            print(f"To: {self.email_to}")
            self.send_email()
        else:
            print("\n⚠️  No alerts found today.")
            print("Patterns were found but current prices don't meet alert conditions:")
            print("  - NEAR: Price must be within 5% below pattern start")
            print("  - ACTIVATED: Price must match pattern start (within 1%)")
            print("  - v200: Price must also be below 200 SMA")
