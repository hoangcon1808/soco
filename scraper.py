#!/usr/bin/env python3
"""
Socolive Stream Scraper - Production Ready
Scrapes live streaming URLs from the Socolive API using Free Proxy Gateways
"""
import requests
import json
import re
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class StreamInfo:
    """Stream information container"""
    room_id: str
    streamer: str
    match_name: str
    category: str
    flv: Optional[str] = None
    hd_flv: Optional[str] = None
    m3u8: Optional[str] = None
    hd_m3u8: Optional[str] = None

class SocoliveScraper:
    """Scraper for Socolive streaming endpoints with automated proxy rotation"""
    BASE_URL = "https://json.vnres.co"
    MATCHES_ENDPOINT = "/match/matches_{date}.json"
    ROOM_ENDPOINT = "/room/{room_id}/detail.json"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        })

    def _fetch_jsonp(self, url: str) -> dict:
        """Fetch JSONP/JSON response via rotation of free gateways to bypass GitHub Action IP blocks"""
        encoded_url = urllib.parse.quote(url)
        
        # Danh sách các Gateway dự phòng khi IP trực tiếp bị chặn 403
        gateways = [
            ("Direct Connection", url),
            ("Codetabs Gateway", f"https://api.codetabs.com/v1/proxy?quest={url}"),
            ("Corsproxy Gateway", f"https://corsproxy.io/?{encoded_url}"),
            ("AllOrigins Gateway", f"https://api.allorigins.win/raw?url={encoded_url}")
        ]
        
        last_error = None
        for name, target_url in gateways:
            try:
                response = self.session.get(target_url, timeout=15)
                response.raise_for_status()
                
                text_clean = response.text.strip()
                if not text_clean:
                    continue
                
                # Giải mã cấu trúc JSONP (bóc tách cặp ngoặc đơn ngoài cùng nếu có)
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
                    
            except Exception as e:
                print(f" [-] {name} tuyến đường thất bại: {e}")
                last_error = e
                continue
                
        raise Exception(f"Tất cả các cổng kết nối đều bị chặn hoặc lỗi dữ liệu. Lỗi cuối: {last_error}")

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
    parser = argparse.ArgumentParser(description='Socolive Stream Scraper Dynamic IP Bypass')
    parser.add_argument('-d', '--date', type=str, help='Định dạng YYYYMMDD (Mặc định: hôm nay)')
    parser.add_argument('-o', '--output', type=str, help='Đường dẫn xuất file dữ liệu JSON')
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
