#!/usr/bin/env python3
"""
Socolive Stream Scraper - Private Proxy & Auto Best Quality Edition
Sử dụng Private Proxy và tự động chọn lọc URL có chất lượng tốt nhất.
"""
from curl_cffi import requests
import json
import urllib.parse
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

    @property
    def best_url(self) -> Optional[str]:
        """Thuật toán tự động lấy link chất lượng tốt nhất"""
        # Ưu tiên 1: HD M3U8 (Chất lượng cao, mượt mà trên web/VLC)
        if self.hd_m3u8: return self.hd_m3u8
        # Ưu tiên 2: HD FLV (Chất lượng cao, tốt cho VLC/PC)
        if self.hd_flv: return self.hd_flv
        # Ưu tiên 3: SD M3U8 (Độ nét tiêu chuẩn, tương thích cao)
        if self.m3u8: return self.m3u8
        # Ưu tiên 4: SD FLV (Dự phòng cuối)
        if self.flv: return self.flv
        return None

class SocoliveScraper:
    BASE_URL = "https://json.vnres.co"
    MATCHES_ENDPOINT = "/match/matches_{date}.json"
    ROOM_ENDPOINT = "/room/{room_id}/detail.json"

    def __init__(self):
        self.session = requests.Session(impersonate="chrome120")
        
        # ---------------------------------------------------------
        # CẤU HÌNH PROXY CÁ NHÂN CỦA BẠN (IP:PORT:USER:PASS)
        # ---------------------------------------------------------
        proxy_url = "http://ZalMQa:BRQrEd@14.250.212.38:36428"
        
        self.session.proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        
        self.session.headers.update({
            'Accept': '*/*',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': 'https://socolive.pro',
            'Referer': 'https://socolive.pro/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def _parse_response(self, text: str) -> dict:
        text_clean = text.strip()
        if not text_clean:
            raise ValueError("Dữ liệu trả về trống rỗng. Có thể proxy bị timeout.")
            
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
        raise ValueError("Cấu trúc JSON không hợp lệ. Đã bị tường lửa Cloudflare chặn ngầm.")

    def _fetch_jsonp(self, url: str) -> dict:
        print(f" [*] Đang cào dữ liệu qua Proxy [14.250.212.38:36428]...")
        try:
            res = self.session.get(url, timeout=15)
            res.raise_for_status()
            return self._parse_response(res.text)
        except Exception as e:
            raise Exception(f"Kết nối Proxy thất bại hoặc bị từ chối: {e}")

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
                    'best_url': s.best_url, # Xuất thẳng link ngon nhất ra ngoài JSON
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
