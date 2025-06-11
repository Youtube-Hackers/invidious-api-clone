from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

YOUTUBE_INNERTUBE_API_KEY = "ligma" # i think inntertube does not require an key anymore, idk
YOUTUBE_API_URL = f"https://www.youtube.com/youtubei/v1/search?key={YOUTUBE_INNERTUBE_API_KEY}"

CLIENT_CONTEXT = {
    "client": {
        "clientName": "WEB",
        "clientVersion": "2.20230615.09.00",
        "hl": "en",
        "gl": "US",
    }
}

def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def extract_length_text(vd):
    length_simple = vd.get("lengthText", {}).get("simpleText")
    length_accessible = (
        vd.get("lengthText", {})
          .get("accessibility", {})
          .get("accessibilityData", {})
          .get("label")
    )
    if length_simple and length_accessible:
        return {
            "accessibility": {
                "accessibilityData": {
                    "label": length_accessible
                }
            },
            "simpleText": length_simple
        }
    return None

def extract_length_text_and_seconds(vd):
    length_obj = vd.get("lengthText", {})
    simple_text = length_obj.get("simpleText")
    accessible_label = (
        length_obj.get("accessibility", {})
        .get("accessibilityData", {})
        .get("label")
    )

    result = None
    seconds = 0

    if simple_text:
        result = {
            "accessibility": {
                "accessibilityData": {
                    "label": accessible_label or ""
                }
            },
            "simpleText": simple_text
        }

        try:
            parts = list(map(int, simple_text.split(":")))
            if len(parts) == 3:
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                seconds = parts[0] * 60 + parts[1]
            elif len(parts) == 1:
                seconds = parts[0]
        except:
            seconds = 0

    return result, seconds

def extract_videos_from_items(items):
    videos = []
    for item in items:
        if "videoRenderer" in item:
            videos.append(item["videoRenderer"])
        elif "carouselShelfRenderer" in item:
            contents = item["carouselShelfRenderer"].get("contents", [])
            videos.extend(extract_videos_from_items(contents))
        elif "richShelfRenderer" in item:
            contents = item["richShelfRenderer"].get("contents", [])
            videos.extend(extract_videos_from_items(contents))
        elif "shelfRenderer" in item:
            contents = item["shelfRenderer"].get("content", {}).get("expandedShelfContentsRenderer", {}).get("items", [])
            videos.extend(extract_videos_from_items(contents))
    return videos


TRENDING_PARAMS = {
    "music": "4gINGgt5dG1hX2NoYXJ0cw%3D%3D",
    "gaming": "4gIcGhpnYW1pbmdfY29ycHVzX21vc3RfcG9wdWxhcg%3D%3D",
    "movies": "4gIKGgh0cmFpbGVycw%3D%3D"
}

def extract_videos_from_items(items):
    videos = []
    for item in items:
        if "videoRenderer" in item:
            videos.append(item["videoRenderer"])
        elif "carouselShelfRenderer" in item or "richShelfRenderer" in item:
            contents = item.get("carouselShelfRenderer", {}).get("contents", []) \
                or item.get("richShelfRenderer", {}).get("contents", [])
            videos.extend(extract_videos_from_items(contents))
        elif "shelfRenderer" in item:
            contents = item.get("shelfRenderer", {}).get("content", {}).get("expandedShelfContentsRenderer", {}).get("items", [])
            videos.extend(extract_videos_from_items(contents))
    return videos

def deduplicate_videos(videos):
    seen = set()
    unique = []
    for v in videos:
        vid = v.get("videoId")
        if vid and vid not in seen:
            seen.add(vid)
            unique.append(v)
    return unique
YOUTUBE_API_BROWSE_URL = f"https://www.youtube.com/youtubei/v1/browse?key={YOUTUBE_INNERTUBE_API_KEY}"

def innertube_trending_v2(trending_type=None, region="US", max_results=50):
    trending_type_key = trending_type.lower() if trending_type else ""
    params = TRENDING_PARAMS.get(trending_type_key, "")

    payload = {
        "context": CLIENT_CONTEXT,
        "browseId": "FEtrending",
    }
    if params:
        payload["params"] = params

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    resp = requests.post(YOUTUBE_API_BROWSE_URL, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    try:
        section_list = data.get("contents", {}) \
            .get("twoColumnBrowseResultsRenderer", {}) \
            .get("tabs", [])[0] \
            .get("tabRenderer", {}) \
            .get("content", {}) \
            .get("sectionListRenderer", {}) \
            .get("contents", [])

        all_items = []
        for section in section_list:
            items = section.get("itemSectionRenderer", {}).get("contents", [])
            all_items.extend(items)

        videos = extract_videos_from_items(all_items)
        videos = deduplicate_videos(videos)
        videos = videos[:max_results]

        def parse_video(vd):
            title = vd.get("title", {}).get("runs", [{}])[0].get("text", "")
            vid = vd.get("videoId", "")
            author = vd.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
            thumbnails = vd.get("thumbnail", {}).get("thumbnails", [])
            view_count_text = vd.get("viewCountText", {}).get("simpleText", "")
            published_text = vd.get("publishedTimeText", {}).get("simpleText", "")
            length_text_obj, length_seconds = extract_length_text_and_seconds(vd)
            return {
                "title": title,
                "videoId": vid,
                "author": author,
                "videoThumbnails": thumbnails,
                "viewCountText": view_count_text,
                "publishedText": published_text,
                "lengthText": length_text_obj,
                "lengthSeconds": length_seconds
            }

        return [parse_video(v) for v in videos]

    except Exception as e:
        print("Trending Parsing Error:", e)
        return []

    
def parse_view_count(view_count_text):
    text = (view_count_text or "").lower().replace("views", "").strip()
    try:
        if "k" in text:
            return int(float(text.replace("k", "")) * 1_000)
        if "m" in text:
            return int(float(text.replace("m", "")) * 1_000_000)
        return int("".join(filter(str.isdigit, text))) or 0
    except:
        return 0

def innertube_search(query, max_results=50):
    payload = {"context": CLIENT_CONTEXT, "query": query, "params": ""}
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

    r = requests.post(YOUTUBE_API_URL, json=payload, headers=headers)
    r.raise_for_status()
    data = r.json()

    videos = []
    sections = (
        data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
    )


    for section in sections:
        items = section.get("itemSectionRenderer", {}).get("contents", [])
        for item in items:
            vd = item.get("videoRenderer")
            if not vd:
                continue

            title = vd["title"]["runs"][0]["text"]
            vid = vd.get("videoId", "")
            owner_runs = vd.get("ownerText", {}).get("runs", [{}])
            author = owner_runs[0].get("text", "")
            nav = owner_runs[0].get("navigationEndpoint", {}).get("browseEndpoint", {})
            authorId = nav.get("browseId", "")
            authorUrl = nav.get("canonicalBaseUrl", "")
            authorVerified = any(
                b.get("metadataBadgeRenderer", {}).get("style") == "BADGE_STYLE_TYPE_VERIFIED"
                for b in vd.get("ownerBadges", [])
            )

            authorThumbnails = (
                vd.get("channelThumbnailSupportedRenderers", {})
                  .get("channelThumbnailWithLinkRenderer", {})
                  .get("thumbnail", {}).get("thumbnails", [])
            )

            videoThumbnails = vd.get("thumbnail", {}).get("thumbnails", [])
            desc = vd.get("descriptionSnippet", {}).get("runs", [{}])[0].get("text", "")
            viewCountText = vd.get("viewCountText", {}).get("simpleText", "")
            viewCount = parse_view_count(viewCountText)
            publishedText = vd.get("publishedTimeText", {}).get("simpleText", "")
            liveNow = any(
                "LIVE" in b.get("metadataBadgeRenderer", {}).get("label", "").upper()
                for b in vd.get("badges", [])
            )
            lengthText, lengthSeconds = extract_length_text_and_seconds(vd)

            videos.append({
                "type": "video",
                "title": title,
                "videoId": vid,
                "author": author,
                "authorId": authorId,
                "authorUrl": authorUrl,
                "authorVerified": authorVerified,
                "authorThumbnails": authorThumbnails,
                "videoThumbnails": videoThumbnails,
                "description": desc,
                "descriptionHtml": "",
                "viewCount": viewCount,
                "viewCountText": viewCountText,
                "published": 0,
                "publishedText": publishedText,
                "lengthSeconds": lengthSeconds,
                "lengthText": lengthText,
                "liveNow": liveNow,
                "premium": False,
                "isUpcoming": False,
                "isNew": False,
                "is4k": False,
                "is8k": False,
                "isVr180": False,
                "isVr360": False,
                "is3d": False,
                "hasCaptions": False
            })

            if len(videos) >= max_results:
                break
        if len(videos) >= max_results:
            break

    return videos

@app.route('/')
def index():
    headers = {
        'Location': 'https://github.com/zUnpaid'
    }
    return "hi", 302, headers

@app.route("/api/v1/search")
def api_search():
    q = request.args.get("q")
    if not q:
        return jsonify({"error": "missing search"}), 400
    try:
        return jsonify(innertube_search(q)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/trending")
def api_trending():
    trending_type = request.args.get("type")
    region = request.args.get("region", "US")
    try:
        videos = innertube_trending_v2(trending_type, region)
        return jsonify(videos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
