#!/usr/bin/env python3
"""
Socolive Stream Scraper
Scrapes live streaming URLs from the Socolive API
"""
# Đổi từ requests sang curl_cffi để vượt tường lửa 403
from curl_cffi import requests
import json
import re
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
    """Scraper for Socolive streaming endpoints"""
    BASE_URL = "https://json.vnres.co"
    MATCHES_ENDPOINT = "/match/matches_{date}.json"
    ROOM_ENDPOINT = "/room/{room_id}/detail.json"

    def __init__(self):
        # Kích hoạt tính năng giả lập trình duyệt Chrome
        self.session = requests.Session(impersonate="chrome")
        
        # Bổ sung các Header giống hệt người dùng thật
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': 'https://socolive.pro',
            'Referer': 'https://socolive.pro/',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site'
        })

    def _fetch_jsonp(self, url: str) -> dict:
        """Fetch JSONP response and parse to JSON"""
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        
        text = response.text
        match = re.match(r'^\w+\((.*)\)$', text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = text
            
        return json.loads(json_str)

    def get_matches(self, date: Optional[datetime] = None) -> List[dict]:
        if date is None:
            date = datetime.now()
            
        date_str = date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}{self.MATCHES_ENDPOINT.format(date=date_str)}"
        data = self._fetch_jsonp(url)
        
        if data.get('code') != 200:
            raise Exception(f"API error: {data.get('msg', 'Unknown error')}")
            
        return data.get('data', [])

    def get_room_detail(self, room_id: str) -> dict:
        url = f"{self.BASE_URL}{self.ROOM_ENDPOINT.format(room_id=room_id)}"
        data = self._fetch_jsonp(url)
        
        if data.get('code') != 200:
            raise Exception(f"API error: {data.get('msg', 'Unknown error')}")
            
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
                    
                    def clean_url(url):
                        if url:
                            return url.replace('\\u003d', '=').replace('\\u0026', '&')
                        return url
                        
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
                    print(f" [-] Error fetching room {room_id}: {e}")
                    
        return streams

    def print_streams(self, streams: List[StreamInfo], format: str = 'table'):
        if format == 'json':
            output = []
            for s in streams:
                output.append({
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
            print(json.dumps(output, indent=2, ensure_ascii=False))
        elif format == 'table':
            print("\n" + "=" * 80)
            print(f"{'Room':<10} {'Streamer':<20} {'Match':<35} {'Category':<15}")
            print("=" * 80)
            for s in streams:
                print(f"{s.room_id:<10} {s.streamer:<20} {s.match_name[:35]:<35} {s.category[:15]:<15}")
            print("=" * 80)
            print(f"Total: {len(streams)} streams\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Scrape Socolive streaming URLs')
    parser.add_argument('-d', '--date', type=str, help='Date in YYYYMMDD format (default: today)')
    parser.add_argument('-f', '--format', choices=['table', 'json', 'm3u8', 'urls'], default='table', help='Output format (default: table)')
    parser.add_argument('-r', '--room', type=str, help='Fetch specific room ID only')
    parser.add_argument('-o', '--output', type=str, help='Output file path (saves as JSON)')
    args = parser.parse_args()

    scraper = SocoliveScraper()
    
    date = None
    if args.date:
        date = datetime.strptime(args.date, "%Y%m%d")

    streams = []
    if args.room:
        print(f"Fetching room {args.room}...")
        try:
            detail = scraper.get_room_detail(args.room)
            stream_data = detail.get('stream', {})
            
            def clean_url(url):
                if url: return url.replace('\\u003d', '=').replace('\\u0026', '&')
                return url
                
            stream = StreamInfo(
                room_id=args.room,
                streamer=detail.get('room', {}).get('anchor', {}).get('nickName', 'Unknown'),
                match_name=detail.get('room', {}).get('title', 'Unknown'),
                category='N/A',
                flv=clean_url(stream_data.get('flv')),
                hd_flv=clean_url(stream_data.get('hdFlv')),
                m3u8=clean_url(stream_data.get('m3u8')),
                hd_m3u8=clean_url(stream_data.get('hdM3u8'))
            )
            streams = [stream]
            scraper.print_streams(streams, args.format)
        except Exception as e:
            print(f"Error: {e}")
    else:
        print(f"Fetching streams for {date.strftime('%Y-%m-%d') if date else 'today'}...")
        streams = scraper.get_all_streams(date)
        scraper.print_streams(streams, args.format)

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
        print(f"JSON data successfully saved to {args.output}")

if __name__ == '__main__':
    main()
