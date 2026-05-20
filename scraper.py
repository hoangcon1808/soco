#!/usr/bin/env python3
"""
Socolive Stream Scraper - Extreme Bypass Edition
Scrapes live streaming URLs using MacOS/Safari impersonation & Google Servers
"""
import json
import re
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

# Sử dụng cả 2 thư viện để linh hoạt vượt rào
from curl_cffi import requests as cffi_requests
import requests as std_requests

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

    def _parse_response(self, text: str) -> dict:
        """Hàm dùng chung để bóc tách dữ liệu JSONP thành JSON chuẩn"""
        text_clean = text.strip()
        if not text_clean:
            raise ValueError("Dữ liệu trả về trống.")
            
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
        raise ValueError("Cấu trúc JSON không hợp lệ hoặc bị Cloudflare chặn ngầm.")

    def _fetch_jsonp(self, url: str) -> dict:
        encoded_url = urllib.parse.quote(url)
        last_error = None
        
        # [Chiến lược 1]: Giả lập trình duyệt Safari trên MacOS
        # Cloudflare rất tin tưởng tín hiệu từ thiết bị Apple
        try:
            print(" [*] Đang thử kết nối trực tiếp (Giả lập Mac/Safari)...")
            session = cffi_requests.Session(impersonate="safari")
            session.headers.update({
                'Accept': '*/*',
                'Accept-Language': 'vi-VN,vi;q=0.9',
                'Origin': 'https://socolive.pro',
                'Referer': 'https://socolive.pro/',
            })
            res = session.get(url, timeout=15)
            res.raise_for_status()
            return self._parse_response(res.text)
        except Exception as e:
            print(f" [-] Kết nối trực tiếp thất bại: {e}")
            last_error = e

        # [Chiến lược 2]: Sử dụng Google OpenSocial Proxy
        # Trạm trung chuyển của chính Google (Dải IP của Google được Whitelist ở mọi nơi)
        try:
            print(" [*] Đang thử kết nối qua trạm trung chuyển Google...")
            google_url = f"https://images1-focus-opensocial.googleusercontent.com/gadgets/proxy?container=focus&refresh=0&url={encoded_url}"
            res = std_requests.get(google_url, timeout=15)
            res.raise_for_status()
            return self._parse_response(res.text)
        except Exception as e:
            print(f" [-] Google Proxy thất bại: {e}")
            last_error = e

        # [Chiến lược 3]: Dự phòng cuối cùng bằng Corsproxy.org
        try:
            print(" [*] Đang thử kết nối qua CorsProxy...")
            cors_url = f"https://corsproxy.org/?{encoded_url}"
            res = std_requests.get(cors_url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}, timeout=15)
            res.raise_for_status()
            return self._parse_response(res.text)
        except Exception as e:
            print(f" [-] CorsProxy thất bại: {e}")
            last_error = e

        raise Exception(f"Tất cả các phương pháp đều bị tường lửa chặn. Lỗi cuối cùng: {last_error}")

    def get_matches(self, date: Optional[datetime] = None) -> List[dict]:
        if date is None:
            date = datetime.now()
            
        date_str = date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}{self.MATCHES_ENDPOINT.format(date=date_str)}"
        data = self._fetch_jsonp(url)
        
        if data.get('code') != 200:
            raise Exception(f"API socolive báo lỗi: {data.get('msg', 'Unknown error')}")
            
        return data.get('data', [])

    def get_room_detail(self, room_id: str) -> dict:
        url = f"{self.BASE_URL}{self.ROOM_ENDPOINT.format(room_id=room_id)}"
        data = self._fetch_jsonp(url)
        
        if data.get('code') != 200:
            raise Exception(f"API socolive báo lỗi: {data.get('msg', 'Unknown error')}")
            
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
                        if url_str:
                            return url_str.replace('\\u003d', '=').replace('\\u0026', '&').replace('\\/', '/')
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
                    print(f" [+] Room {room_id}: {streamer} - {match_name}")
                except Exception as e:
                    print(f" [-] Lỗi tải dữ liệu phòng {room_id}: {e}")
                    
        return streams

    def print_table(self, streams: List[StreamInfo]):
        print("\n" + "=" * 80)
        print(f"{'Phòng':<10} {'Bình Luận Viên':<20} {'Trận Đấu':<35} {'Giải Đấu':<15}")
        print("=" * 80)
        for s in streams:
            print(f"{s.room_id:<10} {s.streamer:<20} {s.match_name[:35]:<35} {s.category[:15]:<15}")
        print("=" * 80)
        print(f"Tổng số: {len(streams)} luồng stream đang hoạt động.\n")

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
        scraper.print_table(streams)
        
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
            print(f" -> Đã lưu cấu trúc dữ liệu JSON thành công vào: {args.output}")
    except Exception as e:
        print(f" Critical Error: {e}")
        exit(1)

if __name__ == '__main__':
    main()
