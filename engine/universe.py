"""
Complete S&P 500 + NASDAQ-100 Universe & Sector Taxonomy for ABI Strategy Terminal.
Includes dynamic fetching for index rebalancing and a full 500+ constituent fallback.
"""

import sys
import pandas as pd

# Core 20 Sector & Industry SPDRs / ETFs
SECTOR_ETFS = {
    "XLV": {"name": "Healthcare", "type": "DEFENSIVE", "benchmark": "SPY"},
    "XME": {"name": "Metals & Mining", "type": "CYCLICAL", "benchmark": "SPY"},
    "ITB": {"name": "Homebuilders", "type": "CYCLICAL", "benchmark": "XLI"},
    "JETS": {"name": "Airlines", "type": "CYCLICAL", "benchmark": "IYT"},
    "TAN": {"name": "Solar", "type": "GROWTH", "benchmark": "XLK"},
    "GDX": {"name": "Gold Miners", "type": "DEFENSIVE", "benchmark": "XME"},
    "IBB": {"name": "Biotech", "type": "GROWTH", "benchmark": "XLV"},
    "XBI": {"name": "Biotech Small Cap", "type": "GROWTH", "benchmark": "XLV"},
    "XLE": {"name": "Energy", "type": "CYCLICAL", "benchmark": "SPY"},
    "IGV": {"name": "Tech Software", "type": "GROWTH", "benchmark": "XLK"},
    "XLF": {"name": "Financials", "type": "CYCLICAL", "benchmark": "SPY"},
    "XLK": {"name": "Technology", "type": "GROWTH", "benchmark": "QQQ"},
    "IHAK": {"name": "Cybersecurity", "type": "GROWTH", "benchmark": "IGV"},
    "XLB": {"name": "Materials", "type": "CYCLICAL", "benchmark": "SPY"},
    "QQQ": {"name": "Nasdaq 100", "type": "GROWTH", "benchmark": "SPY"},
    "KRE": {"name": "Regional Banks", "type": "CYCLICAL", "benchmark": "XLF"},
    "XLC": {"name": "Comm Services", "type": "GROWTH", "benchmark": "SPY"},
    "SMH": {"name": "Semiconductors", "type": "GROWTH", "benchmark": "XLK"},
    "XRT": {"name": "Retail", "type": "CYCLICAL", "benchmark": "XLY"},
    "XLP": {"name": "Consumer Staples", "type": "DEFENSIVE", "benchmark": "SPY"},
    "XLY": {"name": "Consumer Disc", "type": "GROWTH", "benchmark": "SPY"},
    "XLRE": {"name": "Real Estate", "type": "DEFENSIVE", "benchmark": "SPY"},
    "IYT": {"name": "Transportation", "type": "CYCLICAL", "benchmark": "XLI"},
    "XLU": {"name": "Utilities", "type": "DEFENSIVE", "benchmark": "SPY"},
    "XLI": {"name": "Industrials", "type": "CYCLICAL", "benchmark": "SPY"}
}

# Complete S&P 500 + Key NASDAQ-100 Constituent Taxonomy
# Ticker: (Sector, Sub-Sector / Industry)
TICKER_TAXONOMY = {
    "SPY": ("INDEX", "S&P 500 Benchmark"),
    "QQQ": ("INDEX", "Nasdaq 100 Growth"),
    "RSP": ("INDEX", "S&P 500 Equal Weight"),
    "IWM": ("INDEX", "Russell 2000 Small Cap"),
    "VGT": ("INDEX", "Vanguard Information Tech"),
    "VCR": ("INDEX", "Vanguard Consumer Discretionary"),
    "VDC": ("INDEX", "Vanguard Consumer Staples"),
    "VFH": ("INDEX", "Vanguard Financials"),
    "VHT": ("INDEX", "Vanguard Health Care"),
    "VIS": ("INDEX", "Vanguard Industrials"),
    "VDE": ("INDEX", "Vanguard Energy"),
    "VAW": ("INDEX", "Vanguard Materials"),
    "VDC": ("INDEX", "Vanguard Consumer Staples"),
    "VGT": ("INDEX", "Vanguard Information Tech"),
    "VCR": ("INDEX", "Vanguard Consumer Discretionary"),
    "VHT": ("INDEX", "Vanguard Health Care"),
    "VIS": ("INDEX", "Vanguard Industrials"),
    "VDE": ("INDEX", "Vanguard Energy"),
    "VAW": ("INDEX", "Vanguard Materials"),
    "VXUS": ("INDEX", "Vanguard Total International Stock"),
    "BND": ("INDEX", "Vanguard  Total Bond Market"),
    # --- INFORMATION TECHNOLOGY ---
    "AAPL": ("TECH CORE", "Technology Hardware & Storage"),
    "ACN": ("TECH CORE", "IT Consulting & Outsourcing"),
    "ADBE": ("TECH SOFTWARE", "Application Software & Creative"),
    "ADI": ("TECH SEMIS", "Semiconductors & Mixed-Signal"),
    "ADSK": ("TECH SOFTWARE", "3D Design & Engineering Software"),
    "AKAM": ("TECH SOFTWARE", "Edge Computing & CDN Security"),
    "AMAT": ("TECH SEMIS", "Semiconductor Equipment"),
    "AMD": ("TECH SEMIS", "Semiconductors & Processors"),
    "ANET": ("TECH CORE", "Cloud Networking Equipment"),
    "ANSS": ("TECH SOFTWARE", "Simulation Software"),
    "APH": ("TECH CORE", "Electronic Components & Fiber"),
    "AVGO": ("TECH SEMIS", "Semiconductors & Networking"),
    "CDNS": ("TECH SOFTWARE", "Electronic Design Automation"),
    "CDW": ("TECH CORE", "Technology Solutions & Distribution"),
    "CRM": ("TECH SOFTWARE", "Application Software & CRM"),
    "CRWD": ("TECH SOFTWARE", "Endpoint Cybersecurity Software"),
    "CSCO": ("TECH CORE", "Communications Equipment"),
    "DELL": ("TECH CORE", "Servers, Storage & Hardware"),
    "FFIV": ("TECH SOFTWARE", "Application Delivery & Security"),
    "FICO": ("TECH SOFTWARE", "Applied Analytics & Scoring"),
    "FSLR": ("TECH CORE", "Solar Modules & Systems"),
    "FTNT": ("TECH SOFTWARE", "Network & Cloud Security"),
    "GEN": ("TECH SOFTWARE", "Consumer Cybersecurity"),
    "GLW": ("TECH CORE", "Specialty Glass & Optical Fiber"),
    "HPE": ("TECH CORE", "Enterprise Edge & Cloud Compute"),
    "HPQ": ("TECH CORE", "Personal Systems & Printing"),
    "IBM": ("TECH CORE", "IT Consulting & Enterprise Systems"),
    "INTC": ("TECH SEMIS", "Processors & Foundry Services"),
    "INTU": ("TECH SOFTWARE", "Application Software & FinTech"),
    "JBL": ("TECH CORE", "Electronic Manufacturing Solutions"),
    "KEYS": ("TECH CORE", "Electronic Measurement Instruments"),
    "KLAC": ("TECH SEMIS", "Semiconductor Equipment"),
    "LRCX": ("TECH SEMIS", "Semiconductor Equipment"),
    "MCHP": ("TECH SEMIS", "Semiconductors & Microcontrollers"),
    "MPWR": ("TECH SEMIS", "Semiconductors & Power Solutions"),
    "MSFT": ("TECH SOFTWARE", "Systems Software & Cloud"),
    "MSI": ("TECH CORE", "Communications & Public Safety"),
    "MU": ("TECH SEMIS", "Semiconductors & Memory"),
    "NOW": ("TECH SOFTWARE", "Systems Software & IT Workflows"),
    "NTAP": ("TECH CORE", "Hybrid Cloud Data Storage"),
    "NVDA": ("TECH SEMIS", "Semiconductors & AI Compute"),
    "NXPI": ("TECH SEMIS", "Automotive & Industrial Semiconductors"),
    "ON": ("TECH SEMIS", "Semiconductors & Power/Sensors"),
    "ORCL": ("TECH SOFTWARE", "Database & Cloud Infrastructure"),
    "PANW": ("TECH SOFTWARE", "Cybersecurity Software"),
    "PLTR": ("TECH SOFTWARE", "Enterprise AI & Big Data Platforms"),
    "PTC": ("TECH SOFTWARE", "Industrial IoT & CAD Software"),
    "QCOM": ("TECH SEMIS", "Semiconductors & Wireless"),
    "QRVO": ("TECH SEMIS", "RF Connectivity & Power"),
    "ROP": ("TECH SOFTWARE", "Specialized Industrial Software"),
    "SMCI": ("TECH CORE", "AI High-Performance Servers"),
    "SNPS": ("TECH SOFTWARE", "Electronic Design Automation"),
    "STX": ("TECH CORE", "Hard Drives & Data Storage"),
    "SWKS": ("TECH SEMIS", "Mobile Connectivity Chips"),
    "TDY": ("TECH CORE", "Aerospace & Defense Electronics"),
    "TEL": ("TECH CORE", "Electronic Components & Sensors"),
    "TER": ("TECH SEMIS", "Automated Semiconductor Test"),
    "TRMB": ("TECH CORE", "Navigation & Positioning Tech"),
    "TXN": ("TECH SEMIS", "Semiconductors & Analog ICs"),
    "TYL": ("TECH SOFTWARE", "Public Sector Software"),
    "VRSN": ("TECH CORE", "Internet Infrastructure & Domains"),
    "WDC": ("TECH CORE", "Flash Memory & Hard Drives"),
    "WDAY": ("TECH SOFTWARE", "Application Software & HCM"),
    "ZBRA": ("TECH CORE", "Automatic Identification & Barcode"),

    # --- FINANCIALS ---
    "ACGL": ("FINANCIALS", "Property, Casualty & Mortgage Insurance"),
    "AFL": ("FINANCIALS", "Life & Supplemental Health Insurance"),
    "AIG": ("FINANCIALS", "Multi-Line Insurance Services"),
    "AIZ": ("FINANCIALS", "Specialty Insurance Products"),
    "AJG": ("FINANCIALS", "Insurance Brokerage & Risk Management"),
    "ALL": ("FINANCIALS", "Property & Casualty Insurance"),
    "AON": ("FINANCIALS", "Insurance Brokers & Risk Advisory"),
    "AXP": ("FINANCIALS", "Consumer & Commercial Credit Services"),
    "BAC": ("FINANCIALS", "Diversified Mega-Bank"),
    "BEN": ("FINANCIALS", "Global Asset Management"),
    "BK": ("FINANCIALS", "Custody Banking & Investment Management"),
    "BLK": ("FINANCIALS", "Asset Management & Custody"),
    "BRK.B": ("FINANCIALS", "Multi-Sector Holding Conglomerate"),
    "BRO": ("FINANCIALS", "Insurance Wholesale Brokerage"),
    "BX": ("FINANCIALS", "Global Alternative Asset Management"),
    "C": ("FINANCIALS", "Global Diversified Banking"),
    "CB": ("FINANCIALS", "Property & Casualty Insurance"),
    "CBOE": ("FINANCIALS", "Options & Volatility Exchanges"),
    "CFG": ("FINANCIALS", "Regional Commercial Banking"),
    "CINF": ("FINANCIALS", "Property & Casualty Insurance"),
    "CMA": ("FINANCIALS", "Middle Market Commercial Banking"),
    "CME": ("FINANCIALS", "Financial Derivative Exchanges"),
    "COF": ("FINANCIALS", "Consumer Credit & Banking"),
    "EG": ("FINANCIALS", "Global Reinsurance & Specialty"),
    "ERIE": ("FINANCIALS", "Property & Casualty Insurance"),
    "FDS": ("FINANCIALS", "Financial Data & Analytics Platforms"),
    "FITB": ("FINANCIALS", "Regional Commercial Banking"),
    "GL": ("FINANCIALS", "Life & Health Supplemental Insurance"),
    "GS": ("FINANCIALS", "Investment Banking & Capital Markets"),
    "HBAN": ("FINANCIALS", "Regional Commercial Banking"),
    "HIG": ("FINANCIALS", "Property & Casualty Insurance"),
    "ICE": ("FINANCIALS", "Financial Exchanges & Data Services"),
    "IVZ": ("FINANCIALS", "Investment Management & ETFs"),
    "JPM": ("FINANCIALS", "Diversified Mega-Bank"),
    "KEY": ("FINANCIALS", "Regional Commercial Banking"),
    "KKR": ("FINANCIALS", "Global Private Equity & Infrastructure"),
    "L": ("FINANCIALS", "Multi-Line Insurance & Investments"),
    "LNC": ("FINANCIALS", "Life Insurance & Annuities"),
    "MA": ("FINANCIALS", "Global Transaction & Payment Processing"),
    "MCO": ("FINANCIALS", "Financial Information & Credit Ratings"),
    "MET": ("FINANCIALS", "Life & Employee Benefits Insurance"),
    "MKTX": ("FINANCIALS", "Electronic Fixed Income Trading"),
    "MMC": ("FINANCIALS", "Insurance Brokers & Risk Advisory"),
    "MS": ("FINANCIALS", "Investment Banking & Wealth Management"),
    "MSCI": ("FINANCIALS", "Financial Indices & Analytics"),
    "MTB": ("FINANCIALS", "Regional Commercial Banking"),
    "NDAQ": ("FINANCIALS", "Financial Exchanges & Market Technology"),
    "NTRS": ("FINANCIALS", "Wealth Management & Custody Banking"),
    "PFG": ("FINANCIALS", "Retirement Plans & Asset Management"),
    "PGR": ("FINANCIALS", "Property & Casualty Insurance"),
    "PNC": ("FINANCIALS", "Regional Commercial Banking"),
    "PRU": ("FINANCIALS", "Life Insurance & Asset Management"),
    "PYPL": ("FINANCIALS", "Digital Payments & Commerce"),
    "RF": ("FINANCIALS", "Regional Commercial Banking"),
    "RJF": ("FINANCIALS", "Wealth Management & Investment Banking"),
    "SCHW": ("FINANCIALS", "Investment Brokerage & Banking"),
    "SPGI": ("FINANCIALS", "Financial Information & Credit Ratings"),
    "STT": ("FINANCIALS", "Custody Banking & Asset Servicing"),
    "SYF": ("FINANCIALS", "Consumer Credit Financing"),
    "TFC": ("FINANCIALS", "Regional Commercial Banking"),
    "TROW": ("FINANCIALS", "Investment Asset Management"),
    "TRV": ("FINANCIALS", "Property & Casualty Insurance"),
    "UNM": ("FINANCIALS", "Disability & Supplemental Benefits"),
    "USB": ("FINANCIALS", "Diversified Regional Banking"),
    "V": ("FINANCIALS", "Global Transaction & Payment Processing"),
    "WFC": ("FINANCIALS", "Commercial & Retail Banking"),
    "WRB": ("FINANCIALS", "Property & Casualty Insurance"),
    "ZION": ("FINANCIALS", "Western Regional Banking"),

    # --- HEALTHCARE ---
    "A": ("HEALTHCARE", "Life Sciences Equipment & Diagnostics"),
    "ABBV": ("HEALTHCARE", "Biopharmaceuticals & Immunology"),
    "ABT": ("HEALTHCARE", "Medical Devices & Nutritional Products"),
    "ALGN": ("HEALTHCARE", "Orthodontic Medical Devices (Invisalign)"),
    "AMGN": ("HEALTHCARE", "Biotechnology Therapeutics"),
    "BAX": ("HEALTHCARE", "Hospital & Dialysis Medical Products"),
    "BDX": ("HEALTHCARE", "Medical Supplies & Diagnostic Devices"),
    "BIIB": ("HEALTHCARE", "Biotechnology & Neurosciences"),
    "BIO": ("HEALTHCARE", "Life Science Research Products"),
    "BMY": ("HEALTHCARE", "Biopharmaceuticals & Hematology"),
    "BSX": ("HEALTHCARE", "Interventional Medical Devices"),
    "CAH": ("HEALTHCARE", "Health Care Distribution & Logistics"),
    "CI": ("HEALTHCARE", "Health Care Services & Pharmacy Benefit"),
    "COO": ("HEALTHCARE", "Contact Lenses & Women's Healthcare"),
    "COR": ("HEALTHCARE", "Health Care Technology & Sourcing"),
    "CRL": ("HEALTHCARE", "Early-Stage Drug Discovery CRO"),
    "CVS": ("HEALTHCARE", "Health Care Services & Pharmacy Retail"),
    "DGX": ("HEALTHCARE", "Clinical Laboratory Diagnostic Services"),
    "DHR": ("HEALTHCARE", "Life Sciences & Diagnostics Instruments"),
    "DVA": ("HEALTHCARE", "Kidney Dialysis Facilities & Services"),
    "DXCM": ("HEALTHCARE", "Continuous Glucose Monitoring MedTech"),
    "ELV": ("HEALTHCARE", "Managed Health Care & Health Benefits"),
    "EW": ("HEALTHCARE", "Structural Heart Medical Devices"),
    "GEHC": ("HEALTHCARE", "Medical Imaging & Diagnostic Agents"),
    "GILD": ("HEALTHCARE", "Biotechnology & Antiviral Therapies"),
    "HCA": ("HEALTHCARE", "Acute Care Hospital Operations"),
    "HOLX": ("HEALTHCARE", "Women's Health & Mammography Diagnostics"),
    "HSIC": ("HEALTHCARE", "Dental & Medical Office Distribution"),
    "HUM": ("HEALTHCARE", "Managed Health Care & Medicare Services"),
    "IDXX": ("HEALTHCARE", "Veterinary Diagnostics & Instruments"),
    "INCY": ("HEALTHCARE", "Biopharmaceuticals & Targeted Oncology"),
    "IQV": ("HEALTHCARE", "Clinical Research & Healthcare Analytics"),
    "ISRG": ("HEALTHCARE", "Robotic Surgical Systems"),
    "JNJ": ("HEALTHCARE", "Pharmaceuticals & Medical Devices"),
    "LH": ("HEALTHCARE", "Clinical Diagnostics & Drug Development"),
    "LLY": ("HEALTHCARE", "Pharmaceuticals & Incretin Therapies"),
    "MCK": ("HEALTHCARE", "Health Care Distribution & Supply Chain"),
    "MDT": ("HEALTHCARE", "Medical Devices & Cardiac/Surgical"),
    "MOH": ("HEALTHCARE", "Medicaid & Government Managed Care"),
    "MRK": ("HEALTHCARE", "Pharmaceuticals & Oncology"),
    "MRNA": ("HEALTHCARE", "mRNA Vaccines & Biotechnology"),
    "MTD": ("HEALTHCARE", "Precision Instruments & Laboratory Weighing"),
    "PFE": ("HEALTHCARE", "Pharmaceuticals & Vaccines"),
    "PODD": ("HEALTHCARE", "Automated Insulin Delivery MedTech"),
    "REGN": ("HEALTHCARE", "Biotechnology & Antibody Therapeutics"),
    "RMD": ("HEALTHCARE", "Respiratory Medical Devices & Sleep"),
    "RVTY": ("HEALTHCARE", "Life Sciences Instruments & Reagents"),
    "SOLV": ("HEALTHCARE", "Healthcare Purification & Wound Care"),
    "STE": ("HEALTHCARE", "Surgical Sterilization & Infection Prevention"),
    "SYK": ("HEALTHCARE", "Orthopedic & MedTech Equipment"),
    "TECH": ("HEALTHCARE", "Biotechnology Research Reagents"),
    "THC": ("HEALTHCARE", "Hospital & Ambulatory Surgical Centers"),
    "TMO": ("HEALTHCARE", "Life Sciences Tools & Diagnostics"),
    "UHS": ("HEALTHCARE", "Acute Care & Behavioral Health Hospitals"),
    "UNH": ("HEALTHCARE", "Managed Health Care & Health Services"),
    "VRTX": ("HEALTHCARE", "Biotechnology & Rare Diseases"),
    "WAT": ("HEALTHCARE", "Liquid Chromatography & Mass Spec"),
    "WST": ("HEALTHCARE", "Injectable Packaging & Delivery"),
    "XRAY": ("HEALTHCARE", "Professional Dental Consumables"),
    "ZBH": ("HEALTHCARE", "Orthopedic Reconstruction & Sports Med"),
    "ZTS": ("HEALTHCARE", "Animal Health Pharmaceuticals"),

    # --- CONSUMER DISCRETIONARY ---
    "ABNB": ("CONSUMER DISC", "Alternative Vacation Lodging"),
    "AMZN": ("CONSUMER DISC", "Broadline Retail & Cloud Infrastructure"),
    "APTV": ("CONSUMER DISC", "Automotive Architecture & Electronics"),
    "AZO": ("CONSUMER DISC", "Automotive Replacement Parts Retail"),
    "BBWI": ("CONSUMER DISC", "Home Fragrance & Body Care Retail"),
    "BBY": ("CONSUMER DISC", "Consumer Technology Superstores"),
    "BKNG": ("CONSUMER DISC", "Online Travel Agencies & Booking"),
    "BLDR": ("CONSUMER DISC", "Building Components & Framing"),
    "CCL": ("CONSUMER DISC", "Multi-Brand Cruise Vacations"),
    "CMG": ("CONSUMER DISC", "Fast-Casual Mexican Restaurants"),
    "CZR": ("CONSUMER DISC", "Casino Gaming & Resort Entertainment"),
    "DECK": ("CONSUMER DISC", "Footwear & Premium Lifestyle Brands"),
    "DHI": ("CONSUMER DISC", "Single-Family Residential Homebuilding"),
    "DRI": ("CONSUMER DISC", "Full-Service Casual Dining Restaurants"),
    "EBAY": ("CONSUMER DISC", "Online Marketplace & Commerce"),
    "EXPE": ("CONSUMER DISC", "Online Travel Booking & Lodging"),
    "F": ("CONSUMER DISC", "Automotive & Commercial Vehicles"),
    "GM": ("CONSUMER DISC", "Automotive & Autonomous Fleets"),
    "GPC": ("CONSUMER DISC", "Automotive & Industrial Replacement Parts"),
    "GRMN": ("CONSUMER DISC", "GPS Navigation & Smart Wearables"),
    "HAS": ("CONSUMER DISC", "Toys, Board Games & Entertainment"),
    "HD": ("CONSUMER DISC", "Home Improvement Retail"),
    "HLT": ("CONSUMER DISC", "Hotels & Vacation Lodging Chains"),
    "KMX": ("CONSUMER DISC", "Used Vehicle Retail Megastores"),
    "LEN": ("CONSUMER DISC", "Single-Family Residential Homebuilding"),
    "LKQ": ("CONSUMER DISC", "Automotive Recycled & Specialty Parts"),
    "LOW": ("CONSUMER DISC", "Home Improvement Retail"),
    "LULU": ("CONSUMER DISC", "Athletic Apparel & Lifestyle Retail"),
    "LVS": ("CONSUMER DISC", "Integrated Casino Resorts"),
    "MAR": ("CONSUMER DISC", "Hotels, Resorts & Luxury Lodging"),
    "MCD": ("CONSUMER DISC", "Global Fast Food Restaurant Franchise"),
    "MGM": ("CONSUMER DISC", "Casino Resorts & Sports Betting"),
    "MHK": ("CONSUMER DISC", "Flooring & Carpet Manufacturing"),
    "NCLH": ("CONSUMER DISC", "Global Ocean Cruise Vacations"),
    "NKE": ("CONSUMER DISC", "Footwear, Apparel & Equipment"),
    "NVR": ("CONSUMER DISC", "Single-Family Home Construction"),
    "ORLY": ("CONSUMER DISC", "Automotive Aftermarket Parts Retail"),
    "PHM": ("CONSUMER DISC", "Residential Homebuilding"),
    "POOL": ("CONSUMER DISC", "Wholesale Swimming Pool Supplies"),
    "RCL": ("CONSUMER DISC", "Cruise Ship Vacation Fleets"),
    "RL": ("CONSUMER DISC", "Premium Lifestyle Apparel"),
    "ROST": ("CONSUMER DISC", "Off-Price Apparel & Home Retail"),
    "SBUX": ("CONSUMER DISC", "Specialty Eateries & Coffee Retail"),
    "TJX": ("CONSUMER DISC", "Apparel & Home Fashions Off-Price"),
    "TPR": ("CONSUMER DISC", "Luxury Handbags & Accessories (Coach)"),
    "TSCO": ("CONSUMER DISC", "Rural Lifestyle & Farm Supply Retail"),
    "TSLA": ("CONSUMER DISC", "Automobile Manufacturers & Clean Energy"),
    "ULTA": ("CONSUMER DISC", "Beauty Products & Salon Services"),
    "VFC": ("CONSUMER DISC", "Apparel & Footwear Brands (Vans/North Face)"),
    "WHR": ("CONSUMER DISC", "Home Appliances (KitchenAid/Maytag)"),
    "WYNN": ("CONSUMER DISC", "Luxury Casino Resorts & Gaming"),
    "YUM": ("CONSUMER DISC", "Multi-Brand Fast Food Restaurants"),

    # --- CONSUMER STAPLES ---
    "ADM": ("CONSUMER STAPLES", "Agricultural Processing & Commodities"),
    "BF.B": ("CONSUMER STAPLES", "Distilled Spirits (Jack Daniel's)"),
    "BG": ("CONSUMER STAPLES", "Agribusiness & Food Processing"),
    "CAG": ("CONSUMER STAPLES", "Packaged Frozen Foods & Brands"),
    "CHD": ("CONSUMER STAPLES", "Household & Personal Specialty Products"),
    "CL": ("CONSUMER STAPLES", "Oral, Personal & Home Care Products"),
    "CLX": ("CONSUMER STAPLES", "Household Cleaning & Consumer Goods"),
    "COST": ("CONSUMER STAPLES", "Wholesale Membership Clubs"),
    "CPB": ("CONSUMER STAPLES", "Canned Soups & Simple Meals"),
    "DG": ("CONSUMER STAPLES", "Discount Variety Stores"),
    "DLTR": ("CONSUMER STAPLES", "Discount Retail Stores"),
    "EL": ("CONSUMER STAPLES", "Skin Care & Premium Cosmetics"),
    "GIS": ("CONSUMER STAPLES", "Packaged Cereals & Foods"),
    "HRL": ("CONSUMER STAPLES", "Packaged Meat & Food Brands (Spam)"),
    "HSY": ("CONSUMER STAPLES", "Chocolate & Sugar Confectionery"),
    "K": ("CONSUMER STAPLES", "Packaged Snacks & Cereals (Kellanova)"),
    "KDP": ("CONSUMER STAPLES", "Packaged Beverages & Coffee Systems"),
    "KMB": ("CONSUMER STAPLES", "Personal Care Paper Products"),
    "KO": ("CONSUMER STAPLES", "Non-Alcoholic Beverages & Syrups"),
    "KR": ("CONSUMER STAPLES", "Supermarket & Grocery Retail Chains"),
    "KVUE": ("CONSUMER STAPLES", "Consumer Health Brands (Tylenol/Band-Aid)"),
    "LW": ("CONSUMER STAPLES", "Frozen Potato Products & French Fries"),
    "MDLZ": ("CONSUMER STAPLES", "Packaged Snack Foods & Confectionery"),
    "MKC": ("CONSUMER STAPLES", "Spices, Seasonings & Condiments"),
    "MO": ("CONSUMER STAPLES", "Tobacco & Cigarettes"),
    "PEP": ("CONSUMER STAPLES", "Snack Foods & Packaged Beverages"),
    "PG": ("CONSUMER STAPLES", "Personal Care & Household Products"),
    "PM": ("CONSUMER STAPLES", "Smoke-Free & Tobacco Products"),
    "SJM": ("CONSUMER STAPLES", "Coffee, Jams & Pet Foods (Smucker's)"),
    "STZ": ("CONSUMER STAPLES", "Beer, Wine & Spirits Beverage"),
    "SYY": ("CONSUMER STAPLES", "Food Service Distribution"),
    "TAP": ("CONSUMER STAPLES", "Molson Coors Brewing & Beverages"),
    "TGT": ("CONSUMER STAPLES", "General Merchandise & Food Retail"),
    "TSN": ("CONSUMER STAPLES", "Protein Processing (Beef/Pork/Chicken)"),
    "WMT": ("CONSUMER STAPLES", "Hypermarkets & Omnichannel Supercenters"),

    # --- COMMUNICATION SERVICES ---
    "CHTR": ("COMM SERVICES", "Cable & Broadband Services (Spectrum)"),
    "CMCSA": ("COMM SERVICES", "Broadband Cable & Media Networks"),
    "DIS": ("COMM SERVICES", "Entertainment, Media Studios & Parks"),
    "EA": ("COMM SERVICES", "Interactive Entertainment & Video Games"),
    "FOX": ("COMM SERVICES", "News & Sports Broadcasting"),
    "FOXA": ("COMM SERVICES", "News & Sports Media Networks"),
    "GOOG": ("COMM SERVICES", "Search, Cloud & Digital Services"),
    "GOOGL": ("COMM SERVICES", "Search, Cloud & Autonomous AI"),
    "IPG": ("COMM SERVICES", "Advertising & Marketing Services"),
    "LYV": ("COMM SERVICES", "Live Music Events & Ticketing"),
    "META": ("COMM SERVICES", "Social Platforms, Ads & VR/AI"),
    "MTCH": ("COMM SERVICES", "Dating Applications & Platforms"),
    "NFLX": ("COMM SERVICES", "Global Subscription Streaming Entertainment"),
    "NWS": ("COMM SERVICES", "Publishing & Media Content"),
    "NWSA": ("COMM SERVICES", "Publishing & Digital Real Estate Services"),
    "OMC": ("COMM SERVICES", "Advertising & Global Communications"),
    "PARA": ("COMM SERVICES", "Broadcast Television & Studios"),
    "T": ("COMM SERVICES", "Telecommunications & Broadband Services"),
    "TMUS": ("COMM SERVICES", "Wireless Telecom & Mobile Network"),
    "TTWO": ("COMM SERVICES", "Interactive Entertainment & Video Games"),
    "VZ": ("COMM SERVICES", "Wireless Telecom Infrastructure & 5G"),
    "WBD": ("COMM SERVICES", "Global Media & Streaming Entertainment"),

    # --- INDUSTRIALS ---
    "AAL": ("INDUSTRIALS", "Network Passenger Airline"),
    "ALLE": ("INDUSTRIALS", "Security Doors & Access Hardware"),
    "AME": ("INDUSTRIALS", "Electronic Instruments & Electromechanical"),
    "AOS": ("INDUSTRIALS", "Water Heaters & Boilers"),
    "AXON": ("INDUSTRIALS", "Law Enforcement Conducted Energy & Cameras"),
    "BA": ("INDUSTRIALS", "Commercial Jetliners & Defense Space"),
    "CARR": ("INDUSTRIALS", "HVAC, Refrigeration & Building Solutions"),
    "CAT": ("INDUSTRIALS", "Construction & Mining Heavy Machinery"),
    "CHRW": ("INDUSTRIALS", "Freight Brokerage & 3PL Logistics"),
    "CPRT": ("INDUSTRIALS", "Online Salvage Vehicle Auction Services"),
    "CSX": ("INDUSTRIALS", "Eastern Rail Freight Transportation"),
    "CTAS": ("INDUSTRIALS", "Corporate Uniforms & Facility Services"),
    "DAL": ("INDUSTRIALS", "Network Passenger Airline"),
    "DE": ("INDUSTRIALS", "Agricultural, Turf & Heavy Construction Tech"),
    "DOV": ("INDUSTRIALS", "Engineered Systems & Fluids"),
    "EMR": ("INDUSTRIALS", "Industrial Automation & Process Systems"),
    "ETN": ("INDUSTRIALS", "Electrical Power Management & Systems"),
    "EXPD": ("INDUSTRIALS", "Air & Ocean Freight Forwarding"),
    "FAST": ("INDUSTRIALS", "Industrial Fasteners & Supply Chain"),
    "FDX": ("INDUSTRIALS", "Global Express Freight & Air Delivery"),
    "GD": ("INDUSTRIALS", "Aerospace (Gulfstream) & Marine Combat"),
    "GE": ("INDUSTRIALS", "Commercial & Military Aerospace Propulsion"),
    "GEV": ("INDUSTRIALS", "Renewable Energy, Gas Turbines & Electrification"),
    "GNRC": ("INDUSTRIALS", "Backup Power Generators"),
    "HII": ("INDUSTRIALS", "Military Ship & Submarine Construction"),
    "HON": ("INDUSTRIALS", "Industrial Conglomerate & Automation"),
    "HWM": ("INDUSTRIALS", "Lightweight Aerospace Metals & Forgings"),
    "IEX": ("INDUSTRIALS", "Fluid Metering & Health Science"),
    "IR": ("INDUSTRIALS", "Compressors & Vacuum Pumps"),
    "ITW": ("INDUSTRIALS", "Engineered Industrial Fasteners & Systems"),
    "JBHT": ("INDUSTRIALS", "Intermodal & Dedicated Trucking"),
    "JCI": ("INDUSTRIALS", "Building HVAC & Controls"),
    "LHX": ("INDUSTRIALS", "Aerospace Systems & Defense Mission Tech"),
    "LMT": ("INDUSTRIALS", "Aeronautics, Defense & Tactical Missiles"),
    "LUV": ("INDUSTRIALS", "Passenger Airline Transportation"),
    "MAS": ("INDUSTRIALS", "Building Products & Coatings"),
    "NDSN": ("INDUSTRIALS", "Precision Dispensing Equipment"),
    "NOC": ("INDUSTRIALS", "Aerospace & Stealth Defense Systems"),
    "NSC": ("INDUSTRIALS", "Freight Railroad Transportation"),
    "ODFL": ("INDUSTRIALS", "Less-Than-Truckload Freight Transportation"),
    "PCAR": ("INDUSTRIALS", "Heavy Duty Commercial Trucks (Kenworth/Peterbilt)"),
    "PH": ("INDUSTRIALS", "Motion & Fluid Control Technologies"),
    "PNR": ("INDUSTRIALS", "Water Filtration & Pool Systems"),
    "PWR": ("INDUSTRIALS", "Specialty Electric & Infrastructure Contracting"),
    "ROK": ("INDUSTRIALS", "Industrial Automation & Digital"),
    "RSG": ("INDUSTRIALS", "Non-Hazardous Waste Collection & Recycling"),
    "RTX": ("INDUSTRIALS", "Aerospace Defense Systems & Avionics"),
    "SNA": ("INDUSTRIALS", "Professional Tools & Diagnostics"),
    "SWK": ("INDUSTRIALS", "Industrial Tools & Storage"),
    "TDG": ("INDUSTRIALS", "Engineered Aerospace Component Systems"),
    "TT": ("INDUSTRIALS", "Climate Solutions & Commercial HVAC"),
    "TXT": ("INDUSTRIALS", "Aviation (Cessna/Bell) & Industrial"),
    "UAL": ("INDUSTRIALS", "Global Passenger Airline"),
    "UNP": ("INDUSTRIALS", "Class I Freight Railroad Network"),
    "UPS": ("INDUSTRIALS", "Global Package Logistics & Freight"),
    "URI": ("INDUSTRIALS", "Industrial Equipment Rental Fleet"),
    "VRT": ("INDUSTRIALS", "Data Center Thermal Cooling & Power"),
    "WAB": ("INDUSTRIALS", "Locomotives & Rail Freight Equipment"),
    "WM": ("INDUSTRIALS", "Environmental Waste Management & Recycling"),
    "XYL": ("INDUSTRIALS", "Water Technology & Smart Metering"),

    # --- MATERIALS ---
    "ALB": ("MATERIALS", "Lithium Refining & Specialty Chemicals"),
    "AMCR": ("MATERIALS", "Rigid & Flexible Packaging"),
    "APD": ("MATERIALS", "Industrial Gases & Equipment"),
    "AVY": ("MATERIALS", "Pressure-Sensitive Labeling"),
    "BALL": ("MATERIALS", "Metal Beverage Packaging"),
    "CE": ("MATERIALS", "Specialty Materials & Acetyl"),
    "CF": ("MATERIALS", "Nitrogen Fertilizer & Clean Ammonia"),
    "CTVA": ("MATERIALS", "Crop Protection & Agricultural Seed"),
    "DD": ("MATERIALS", "Specialty Materials & Electronics Polymers"),
    "DOW": ("MATERIALS", "Commodity & Specialty Chemicals"),
    "ECL": ("MATERIALS", "Water Purification & Hygiene Solutions"),
    "EMN": ("MATERIALS", "Diversified Chemicals"),
    "FCX": ("MATERIALS", "Copper & Gold Mining Operations"),
    "FMC": ("MATERIALS", "Agricultural Sciences"),
    "IFF": ("MATERIALS", "Specialty Chemicals & Ingredients"),
    "IP": ("MATERIALS", "Corrugated Packaging & Cellulose"),
    "LIN": ("MATERIALS", "Industrial Gases, Hydrogen & Cryogenics"),
    "MLM": ("MATERIALS", "Heavy Building Aggregates & Asphalt"),
    "MOS": ("MATERIALS", "Crop Nutrition & Potash"),
    "NEM": ("MATERIALS", "Gold & Precious Metals Mining"),
    "NUE": ("MATERIALS", "Steel Mills & Scrap Metal Recycling"),
    "PKG": ("MATERIALS", "Paper & Packaging Containers"),
    "PPG": ("MATERIALS", "Industrial Coatings & Paints"),
    "SEE": ("MATERIALS", "Protective & Cryovac Packaging"),
    "SHW": ("MATERIALS", "Architectural Paints, Coatings & Finishes"),
    "STLD": ("MATERIALS", "Steel Fabrication & Recycling"),
    "SW": ("MATERIALS", "Global Corrugated & Consumer Packaging"),
    "VMC": ("MATERIALS", "Aggregates, Crushed Stone & Concrete"),

    # --- ENERGY ---
    "APA": ("ENERGY", "Oil & Gas Exploration & Production"),
    "BKR": ("ENERGY", "Energy Technology & Turbomachinery"),
    "COP": ("ENERGY", "Oil & Gas Exploration & Production"),
    "CTRA": ("ENERGY", "Natural Gas & Oil Exploration"),
    "CVX": ("ENERGY", "Integrated Global Energy Conglomerate"),
    "DVN": ("ENERGY", "Multi-Basin Oil & Gas E&P"),
    "EOG": ("ENERGY", "Crude Oil & Natural Gas E&P"),
    "EQT": ("ENERGY", "Natural Gas Exploration & Production"),
    "FANG": ("ENERGY", "Permian Basin Pure-Play E&P"),
    "HAL": ("ENERGY", "Oilfield Services & Drilling Equipment"),
    "HES": ("ENERGY", "Exploration & Offshore Oil Production"),
    "KMI": ("ENERGY", "Energy Pipeline Infrastructure & Storage"),
    "MPC": ("ENERGY", "Petroleum Refining & Marketing"),
    "OKE": ("ENERGY", "Natural Gas Midstream Infrastructure"),
    "OXY": ("ENERGY", "Oil & Gas E&P & Direct Air Capture"),
    "PSX": ("ENERGY", "Petroleum Refining, Logistics & Chemical"),
    "SLB": ("ENERGY", "Oilfield Equipment & Global Technology"),
    "TRGP": ("ENERGY", "Midstream Natural Gas Gathering"),
    "VLO": ("ENERGY", "Petroleum Refining & Renewable Diesel"),
    "WMB": ("ENERGY", "Natural Gas Pipeline Infrastructure"),
    "XOM": ("ENERGY", "Integrated Global Oil, Gas & Petrochemical"),

    # --- REAL ESTATE ---
    "AMH": ("REAL ESTATE", "Single-Family Rental Homes"),
    "AMT": ("REAL ESTATE", "Wireless Communications Towers"),
    "ARE": ("REAL ESTATE", "Life Science Office & Lab Campuses"),
    "AVB": ("REAL ESTATE", "High-End Coastal Apartment Communities"),
    "BXP": ("REAL ESTATE", "Premier Workplace Office Properties"),
    "CBRE": ("REAL ESTATE", "Commercial Real Estate Services & Advisory"),
    "CCI": ("REAL ESTATE", "Cell Towers & Fiber Solutions"),
    "CPT": ("REAL ESTATE", "Multi-Family Apartment Communities"),
    "DLR": ("REAL ESTATE", "Enterprise Cloud Data Centers"),
    "DOC": ("REAL ESTATE", "Healthcare & Medical Office Buildings"),
    "EQIX": ("REAL ESTATE", "Global Interconnection Data Centers"),
    "EQR": ("REAL ESTATE", "Urban Coastal Multi-Family Rentals"),
    "ESS": ("REAL ESTATE", "West Coast Multi-Family Communities"),
    "EXR": ("REAL ESTATE", "Self-Storage Storage Real Estate"),
    "FRT": ("REAL ESTATE", "High-End Mixed-Use Retail Properties"),
    "HST": ("REAL ESTATE", "Luxury Hotel & Resort Properties"),
    "INVH": ("REAL ESTATE", "Single-Family Rental Homes"),
    "IRM": ("REAL ESTATE", "Physical Records Storage & Data Centers"),
    "KIM": ("REAL ESTATE", "Grocery-Anchored Shopping Centers"),
    "MAA": ("REAL ESTATE", "Sunbelt Multi-Family Apartment Communities"),
    "O": ("REAL ESTATE", "Single-Tenant Commercial Real Estate"),
    "PLD": ("REAL ESTATE", "Industrial Logistics & Distribution Warehouses"),
    "PSA": ("REAL ESTATE", "Self-Storage Facilities"),
    "REG": ("REAL ESTATE", "Suburban Grocery Shopping Centers"),
    "SBAC": ("REAL ESTATE", "Wireless Communication Towers"),
    "SPG": ("REAL ESTATE", "Retail Shopping Malls & Outlets"),
    "UDR": ("REAL ESTATE", "Urban Multi-Family Apartments"),
    "VICI": ("REAL ESTATE", "Gaming, Hospitality & Entertainment REIT"),
    "VTR": ("REAL ESTATE", "Seniors Housing & Healthcare"),
    "WELL": ("REAL ESTATE", "Healthcare & Senior Housing Infrastructure"),
    "WY": ("REAL ESTATE", "Timberland & Forest Products REIT"),

    # --- UTILITIES ---
    "AEP": ("UTILITIES", "Electric Power Transmission & Generation"),
    "AES": ("UTILITIES", "Global Power Generation & Renewables"),
    "ATO": ("UTILITIES", "Regulated Natural Gas Distribution"),
    "AWK": ("UTILITIES", "Regulated Water & Wastewater Services"),
    "CEG": ("UTILITIES", "Nuclear & Zero-Carbon Energy Generation"),
    "CMS": ("UTILITIES", "Michigan Electric & Natural Gas Utility"),
    "CNP": ("UTILITIES", "Electric Transmission & Natural Gas"),
    "D": ("UTILITIES", "Regulated Electric Utility Services"),
    "DUK": ("UTILITIES", "Regulated Electric & Natural Gas Utility"),
    "ED": ("UTILITIES", "New York Regulated Electric & Gas"),
    "EIX": ("UTILITIES", "Southern California Electric Utility"),
    "ES": ("UTILITIES", "New England Electric & Natural Gas"),
    "ETR": ("UTILITIES", "Gulf Coast Electric Utility & Nuclear"),
    "EVRG": ("UTILITIES", "Kansas & Missouri Electric Power"),
    "EXC": ("UTILITIES", "Electric & Natural Gas Transmission"),
    "FE": ("UTILITIES", "Mid-Atlantic & Midwest Electric Transmission"),
    "LNT": ("UTILITIES", "Midwestern Regulated Electric Utility"),
    "NEE": ("UTILITIES", "Clean Energy & Regulated Florida Power"),
    "NI": ("UTILITIES", "Natural Gas & Electric Utility"),
    "NRG": ("UTILITIES", "Competitive Power Generation & Retail"),
    "PCG": ("UTILITIES", "California Electric & Natural Gas Utility"),
    "PEG": ("UTILITIES", "Regulated Electric Transmission & Gas"),
    "PPL": ("UTILITIES", "Regulated Electric Utility Transmission"),
    "SRE": ("UTILITIES", "Energy Infrastructure & Natural Gas Distribution"),
    "SO": ("UTILITIES", "Electric Utility Power Generation"),
    "VST": ("UTILITIES", "Power Generation & Retail Electricity"),
    "WEC": ("UTILITIES", "Regulated Electric & Natural Gas"),
    "XEL": ("UTILITIES", "Regulated Electric Utility & Clean Energy"),

    # --- Foreign / Mega Growth (S&P Ineligible) ---
    "SHOP": ("TECH SOFTWARE", "E-Commerce Cloud Operating System"),
    "MELI": ("CONSUMER DISC", "Latin American E-Commerce & FinTech"),
    "SPOT": ("COMM SERVICES", "Audio Streaming & Podcasts"),
    "ARM":  ("TECH SEMIS", "RISC Architecture & Semiconductor IP"),

    # --- Crypto, Blockchain & Compute ---
    "MSTR": ("CRYPTO", "Enterprise Software & Bitcoin Treasury"),
    "COIN": ("CRYPTO", "Digital Asset Exchange & Custody"),
    "CRCL": ("CRYPTO", "Stablecoin Infrastructure & Payments"),
    "RIOT": ("CRYPTO", "Digital Asset Infrastructure & Mining"),
    "CIFR": ("CRYPTO", "Industrial Data Center Mining"),
    "WULF": ("CRYPTO", "Zero-Carbon Digital Asset Mining"),
    "IREN": ("CRYPTO", "Next-Gen AI Data Centers & Mining"),
    "MARA": ("CRYPTO", "Digital Asset Compute & Mining"),
    "CLSK": ("CRYPTO", "Data Center Infrastructure & Bitcoin Mining"),

    # --- FinTech, Lending & Retail Brokerage ---
    "HOOD": ("FINANCIALS", "Retail Brokerage & Digital Assets"),
    "SOFI": ("FINANCIALS", "Digital Banking, Lending & FinTech"),
    "AFRM": ("FINANCIALS", "Buy-Now-Pay-Later Consumer FinTech"),
    "RKT":  ("FINANCIALS", "Mortgage Origination & FinTech Platforms"),
    "UPST": ("FINANCIALS", "AI-Driven Consumer Credit Lending"),

    # --- High-Beta AI, Cloud & Automation ---
    "APP":  ("TECH SOFTWARE", "AI-Driven Marketing Software"),
    "RDDT": ("COMM SERVICES", "Online Communities & Discourse Data"),
    "ZETA": ("TECH SOFTWARE", "AI Marketing Automation Platforms"),
    "TEM":  ("HEALTHCARE", "AI Precision Medicine & Diagnostics"),
    "SYM":  ("INDUSTRIALS", "Supply Chain AI & Warehouse Robotics"),
    "ALAB": ("TECH SEMIS", "AI Connectivity & Cloud Infrastructure"),

    # --- High-Growth Consumer & Retail ---
    "ELF":  ("CONSUMER STAPLES", "Cruelty-Free Cosmetics & Skincare"),
    "ANF":  ("CONSUMER DISC", "Lifestyle Apparel Retail Stores"),
    "RIVN": ("CONSUMER DISC", "Electric Adventure Vehicles & Vans"),
    "CAVA": ("CONSUMER DISC", "Fast-Casual Mediterranean Dining"),
    "DKNG": ("CONSUMER DISC", "Online Sports Betting & iGaming"),
    "DUOL": ("TECH SOFTWARE", "Mobile Language & Learning Tech"),

    # --- Healthcare & Biotech Momentum ---
    "HIMS": ("HEALTHCARE", "Direct-to-Consumer Telehealth & Pharma"),
    "GRAL": ("HEALTHCARE", "Early Multi-Cancer Screening Diagnostics"),
    "OSCR": ("HEALTHCARE", "Direct-to-Consumer Health Insurance Tech"),

    # --- Aerospace, Defense & Space ---
    "ASTS": ("COMM SERVICES", "Space-Based Cellular Broadband Network"),
    "RKLB": ("INDUSTRIALS", "Launch Services & Space Systems"),
    "VSAT": ("TECH CORE", "Satellite Communications & Defense Broadband"),
    "HSAI": ("TECH CORE", "LiDAR Sensors & Autonomous Navigation"),

    # --- Energy, Commodities & Industrials ---
    "BTU":  ("ENERGY", "Thermal & Metallurgical Coal Mining"),
    "AMR":  ("ENERGY", "Metallurgical Coal Mining Pure-Play"),
    "PTEN": ("ENERGY", "Contract Land Drilling & Pressure Pumping"),
    "OII":  ("ENERGY", "Subsea Offshore Robotics & Engineering"),

    # --- Foreign Listings Excluded from S&P 500 ---
    "ASML": ("TECH SEMIS", "Photolithography Semiconductor Systems"),
    "PDD":  ("CONSUMER DISC", "Cross-Border E-Commerce & Marketplace (Temu)"),

    # --- High Implied Volatility & Earnings Momentum ---
    "MRVL": ("TECH SEMIS", "Data Infrastructure & Custom AI ASICs"),
    "DDOG": ("TECH SOFTWARE", "Cloud Monitoring & Observability"),
    "DASH": ("CONSUMER DISC", "Local On-Demand Logistics & Delivery"),
    "ALNY": ("HEALTHCARE", "RNA Interference (RNAi) Therapeutics"),

    # --- Pure-Play AI Infrastructure ("Neoclouds") ---
    "CRWV": ("TECH SOFTWARE", "GPU Cloud Infrastructure & AI Compute (CoreWeave)"),
    "NBIS": ("TECH SOFTWARE", "AI Infrastructure & Cloud GPU Clusters (Nebius Group)"),
    
    # --- INFORMATION TECHNOLOGY (SEMIS & HARDWARE) ---
    "ASML": ("TECH SEMIS", "Photolithography Semiconductor Systems"),
    "MRVL": ("TECH SEMIS", "Data Infrastructure & Custom AI ASICs"),
    "LITE": ("TECH CORE", "Optical Communications & Photonic Subsystems"),

    # --- INFORMATION TECHNOLOGY (SOFTWARE & CLOUD) ---
    "ADP":  ("TECH SOFTWARE", "Cloud Human Capital Management & Payroll"),
    "PAYX": ("TECH SOFTWARE", "Payroll, HR & Benefits Outsourcing"),
    "DDOG": ("TECH SOFTWARE", "Cloud Monitoring & Observability"),
    "TEAM": ("TECH SOFTWARE", "Team Collaboration & Workflow Software"),
    "CRWV": ("TECH SOFTWARE", "GPU Cloud Infrastructure & AI Compute"),
    "NBIS": ("TECH SOFTWARE", "AI Infrastructure & Cloud GPU Clusters"),

    # --- CONSUMER DISCRETIONARY & PLATFORMS ---
    "PDD":  ("CONSUMER DISC", "Cross-Border E-Commerce & Marketplace (Temu/Pinduoduo)"),
    "DASH": ("CONSUMER DISC", "Local On-Demand Logistics & Delivery"),

    # --- CONSUMER STAPLES ---
    "MNST": ("CONSUMER STAPLES", "Energy Drinks & Functional Beverages"),
    "CCEP": ("CONSUMER STAPLES", "Bottling & Distribution Partner (Coca-Cola Europacific)"),

    # --- HEALTHCARE & BIOTECH ---
    "ALNY": ("HEALTHCARE", "RNA Interference (RNAi) Therapeutics"),

    # --- INDUSTRIALS & INFRASTRUCTURE ---
    "FER":  ("INDUSTRIALS", "Global Transportation Infrastructure & Toll Roads"),
}

def fetch_live_sp500_constituents():
    """
    Dynamically fetches official S&P 500 constituents from Wikipedia.
    Disabled due to upstream rate-limiting/403 blocks; falls back to static taxonomy.
    """
    # NOTE: Scraping disabled to prevent Wikipedia 403/parsing errors and network stalls.
    # To re-enable in the future, Wikimedia requires a dedicated User-Agent policy
    # (e.g., 'User-Agent': 'MyAppName/1.0 (contact@domain.com)').
    
    # try:
    #     import urllib.request
    #     url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    #     req = urllib.request.Request(
    #         url,
    #         headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    #     )
    #     with urllib.request.urlopen(req) as resp:
    #         tables = pd.read_html(resp.read())
    #     df = tables[0]
    #     live_taxonomy = {}
    #     for _, row in df.iterrows():
    #         sym = str(row['Symbol']).replace('.', '-')
    #         gics_sector = str(row['GICS Sector']).upper()
    #         gics_sub = str(row.get('GICS Sub-Industry', ''))
    #         
    #         # Map to Strategy Sector buckets
    #         if "INFORMATION TECHNOLOGY" in gics_sector:
    #             if any(k in gics_sub.lower() for k in ["semiconductor", "equipment"]):
    #                 sec = "TECH SEMIS"
    #             elif any(k in gics_sub.lower() for k in ["software", "internet"]):
    #                 sec = "TECH SOFTWARE"
    #             else:
    #                 sec = "TECH CORE"
    #         elif "FINANCIALS" in gics_sector:
    #             sec = "FINANCIALS"
    #         elif "HEALTH CARE" in gics_sector:
    #             sec = "HEALTHCARE"
    #         elif "ENERGY" in gics_sector:
    #             sec = "ENERGY"
    #         elif "INDUSTRIALS" in gics_sector:
    #             sec = "INDUSTRIALS"
    #         elif "CONSUMER DISCRETIONARY" in gics_sector:
    #             sec = "CONSUMER DISC"
    #         elif "CONSUMER STAPLES" in gics_sector:
    #             sec = "CONSUMER STAPLES"
    #         elif "COMMUNICATION" in gics_sector:
    #             sec = "COMM SERVICES"
    #         elif "MATERIALS" in gics_sector:
    #             sec = "MATERIALS"
    #         elif "REAL ESTATE" in gics_sector:
    #             sec = "REAL ESTATE"
    #         elif "UTILITIES" in gics_sector:
    #             sec = "UTILITIES"
    #         else:
    #             sec = gics_sector
    #             
    #         live_taxonomy[sym] = (sec, gics_sub)
    #     return live_taxonomy
    # except Exception as e:
    #     print(f"[!] Dynamic S&P 500 fetch skipped ({e}). Using built-in master taxonomy.")

    # Safe return: Use the static taxonomy defined in the module
    return TICKER_TAXONOMY

def get_complete_taxonomy():
    """Returns the merged taxonomy: dynamic live S&P 500 (if online) merged with built-in master list."""
    live = fetch_live_sp500_constituents()
    merged = dict(TICKER_TAXONOMY)
    if live:
        merged.update(live)
    return merged

BENCHMARK_INDICES = ["SPY", "QQQ", "RSP", "IWM"]

def get_full_universe():
    """Returns sorted unique tickers across full universe + ETFs + benchmark indices."""
    tax = get_complete_taxonomy()
    tickers = set(tax.keys()).union(set(SECTOR_ETFS.keys()))
    for idx_sym in BENCHMARK_INDICES:
        tickers.add(idx_sym)
    return sorted(list(tickers))

if __name__ == "__main__":
    uni = get_full_universe()
    print(f"Total tickers in full S&P 500 + NASDAQ + ETF universe: {len(uni)}")
