#!/usr/bin/env python3
"""
Socolive Stream Scraper - Ultimate Proxy Hunter Edition
Bypasses aggressive WAFs by cascading through Gateways and dynamically scraping Free Proxies.
"""
from curl_cffi import requests as cffi_requests
import requests as std_requests
import json
import re
import urllib.parse
import random
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class StreamInfo:
    room_id: str
    streamer: str
    match_name: str
    category: str
    flv: Optional[str] = None
    hd_flv: Optional[str] = None
    m3u8: Optional[str] = None
    hd_m3u8: Optional[str] = None

class SocoliveScraper:
    BASE_URL = "https://json.vnres.co"
    MATCHES_ENDPOINT = "/match/matches_{date}.json"
    ROOM_ENDPOINT = "/room/{room_id}/detail.json"

    def __init__(self):
        self.session = cffi_requests.Session(impersonate="chrome120")
        self.session.headers.update({
            'Accept': '*/*',
            'Accept-Language': 'vi-VN,vi;q=0.9',
            'Origin': 'https://socolive.pro',
            'Referer': 'https://socolive.pro/',
        })
        self.working_proxy = None  # Biến lưu trữ Proxy nếu tìm thấy cổng vượt tường lửa

    def _parse_response(self, text: str) -> dict:
        """Kiểm tra và bóc tách dữ liệu. Nếu dính HTML Cloudflare, hàm sẽ văng lỗi để đổi Proxy"""
        text_clean = text.strip()
        if not text_clean:
            raise ValueError("Dữ liệu trả về trống rỗng.")
            
        if text_clean.startswith('{') or text_clean.startswith('['):
            json_str = text_clean
        else:
            start = text_clean.find('(')
            end = text_clean.rfind(')')
            if start != -1 and end != -1:
                json_str = text_clean[start+1:end]
            else:
                json_str = text_clean
        
        data = json.loads(json_str)
        if isinstance(data, dict) and 'code' in data:
            return data
        raise ValueError("Cấu trúc JSON không hợp lệ (Có thể đang bị chặn ngầm).")

    def _fetch_jsonp(self, url: str) -> dict:
        # [CHIẾN LƯỢC 1]: Dùng Proxy đã xác nhận hoạt động hoặc Thử kết nối trực tiếp
        if self.working_proxy:
            try:
                res = self.session.get(url, proxies=self.working_proxy, timeout=10)
                return self._parse_response(res.text)
            except:
                self.working_proxy = None # Proxy chết, xóa để tìm cái khác
                
        try:
            res = self.session.get(url, timeout=10)
            return self._parse_response(res.text)
        except:
            pass

        # [CHIẾN LƯỢC 2]: Mượn đường qua các Gateways công cộng (dùng API chuẩn để tránh lỗi 500)
        encoded_url = urllib.parse.quote(url)
        gateways = [
            ("AllOrigins", f"https://api.allorigins.win/get?url={encoded_url}"),
            ("CodeTabs", f"https://api.codetabs.com/v1/proxy?quest={url}"),
            ("CorsProxy", f"https://corsproxy.io/?{encoded_url}")
        ]
        
        for name, gw_url in gateways:
            try:
                res = std_requests.get(gw_url, timeout=15)
                if res.status_code == 200:
                    text = res.text
                    if name == "AllOrigins":
                        data = res.json()
                        if data.get('status', {}).get('http_code') == 200:
                            text = data.get('contents', '')
                        else:
                            continue
                    if text:
                        return self._parse_response(text)
            except:
                continue

        # [CHIẾN LƯỢC 3]: Radar săn IP Proxy miễn phí
        print("\n [*] Tường lửa chặn quá gắt. Đang kích hoạt Radar tải danh sách Proxy miễn phí thế giới...")
        proxy_sources = [
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=all&anonymity=all",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
        ]
        
        proxies = []
        for src in proxy_sources:
            try:
                res = std_requests.get(src, timeout=10)
                proxies.extend([p.strip() for p in res.text.split('\n') if p.strip()])
            except:
                pass
                
        # Lọc bỏ khoảng trắng và xáo trộn ngẫu nhiên để không bị trùng lặp
        proxies = list(set([p for p in proxies if p]))
        random.shuffle(proxies)
        
        print(f" [*] Đã thu thập được {len(proxies)} IP. Bắt đầu dò tìm khe hở tường lửa (Thử max 30 IP)...")
        
        for p in proxies[:30]:
            proxy_dict = {"http": f"http://{p}", "https": f"http://{p}"}
            try:
                # Dùng curl_cffi kết hợp Proxy để có xác suất qua ải cao nhất
                res = self.session.get(url, proxies=proxy_dict, timeout=7)
                data = self._parse_response(res.text)
                
                print(f" [+] BINGOOO! Đã đục thủng tường lửa bằng Proxy: {p}")
                self.working_proxy = proxy_dict  # Lưu lại để dùng cho các request tiếp theo
                return data
            except:
                continue

        raise Exception("Vô phương cứu chữa. Toàn bộ Trực tiếp, Gateways và Hàng chục Proxy đều thất bại. Hãy thử lại sau.")

    def get_matches(self, date: Optional[datetime] = None) -> List[dict]:
        if date is None:
            date = datetime.now()
            
        date_str = date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}{self.MATCHES_ENDPOINT.format(date=date_str)}"
        data = self._fetch_jsonp(url)
        return data.get('data', [])

    def get_room_detail(self, room_id: str) -> dict:
        url = f"{self.BASE_URL}{self.ROOM_ENDPOINT.format(room_id=room_id)}"
        data = self._fetch_jsonp(url)
        return data.get('data', {})

    def get_all_streams(self, date: Optional[datetime] = None) -> List[StreamInfo]:
        matches = self.get_matches(date)
        streams = []
        seen_rooms = set()
        
        for match in matches:
            match_name = f"{match.get('hostName', '?')} vs {match.get('guestName', '?')}"
            category = match.get('subCateName', match.get('categoryName', 'Unknown'))
            
            for anchor in match.get('anchors', []):
                room_id = anchor.get('anchor', {}).get('roomNum') or str(anchor.get('uid', ''))
                if not room_id or room_id in seen_rooms:
                    continue
                    
                seen_rooms.add(room_id)
                streamer = anchor.get('nickName', 'Unknown')
                
                try:
                    detail = self.get_room_detail(room_id)
                    stream_data = detail.get('stream', {})
                    
                    def clean_url(url_str):
                        if url_str: return url_str.replace('\\u003d', '=').replace('\\u0026', '&').replace('\\/', '/')
                        return url_str
                        
                    stream_info = StreamInfo(
                        room_id=room_id,
                        streamer=streamer,
                        match_name=match_name,
                        category=category,
                        flv=clean_url(stream_data.get('flv')),
                        hd_flv=clean_url(stream_data.get('hdFlv')),
                        m3u8=clean_url(stream_data.get('m3u8')),
                        hd_m3u8=clean_url(stream_data.get('hdM3u8'))
                    )
                    streams.append(stream_info)
                    print(f"  -> Lấy thành công link phòng {room_id}: {streamer}")
                except Exception as e:
                    print(f"  -> Lỗi lấy link phòng {room_id}: {e}")
                    
        return streams

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--date', type=str)
    parser.add_argument('-o', '--output', type=str)
    args = parser.parse_args()

    scraper = SocoliveScraper()
    date = datetime.strptime(args.date, "%Y%m%d") if args.date else None

    print(f"Bắt đầu thu thập dữ liệu luồng stream...")
    try:
        streams = scraper.get_all_streams(date)
        
        print("\n" + "=" * 80)
        print(f"Tổng số: {len(streams)} luồng stream đang hoạt động.")
        print("=" * 80)
        
        if args.output and streams:
            output_data = []
            for s in streams:
                output_data.append({
                    'room_id': s.room_id,
                    'streamer': s.streamer,
                    'match': s.match_name,
                    'category': s.category,
                    'urls': {
                        'flv': s.flv,
                        'hd_flv': s.hd_flv,
                        'm3u8': s.m3u8,
                        'hd_m3u8': s.hd_m3u8
                    }
                })
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f" -> Đã lưu JSON thành công vào: {args.output}")
    except Exception as e:
        print(f" Critical Error: {e}")
        exit(1)

if __name__ == '__main__':
    main()
