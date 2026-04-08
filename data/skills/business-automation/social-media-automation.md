---
name: Social Media Content Automation
description: Automate social media content creation, scheduling, and engagement monitoring across platforms
version: "1.0.0"
author: ROOT
tags: [business-automation, social-media, content, scheduling, LinkedIn, Twitter]
platforms: [all]
difficulty: beginner
---

# Social Media Content Automation

Build a content machine that publishes consistently without requiring daily manual effort.

## Content Strategy Framework

### Content Pillar System (80/20 Rule)

```
80% Value Content:
  - Educational posts (industry insights, how-tos)
  - Behind-the-scenes (team, process, culture)
  - Data and research (original or curated)
  - Case studies and success stories

20% Promotional Content:
  - Product announcements
  - Feature highlights
  - Offers and trials
  - Social proof and testimonials
```

### Content Calendar Template

```python
WEEKLY_CONTENT_CALENDAR = {
    "Monday": {"theme": "educational", "format": "long_form_insight", "platform": "LinkedIn"},
    "Tuesday": {"theme": "product", "format": "short_demo_video", "platform": "Twitter/X"},
    "Wednesday": {"theme": "community", "format": "question_poll", "platform": "LinkedIn"},
    "Thursday": {"theme": "industry_news", "format": "commentary", "platform": "Twitter/X"},
    "Friday": {"theme": "team_culture", "format": "photo_story", "platform": "LinkedIn"},
}
```

## AI Content Generation Pipeline

```python
from anthropic import Anthropic
import feedparser

client = Anthropic()

def generate_linkedin_post(topic: str, company_context: str, tone: str = "professional") -> dict:
    """Generate LinkedIn post from topic and company context."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": f"""Write a LinkedIn post about: {topic}

Company context: {company_context}
Tone: {tone}
Goal: Drive engagement and demonstrate thought leadership

Requirements:
- Hook in first line (no "I'm excited to share...")
- 150-300 words optimal length
- 3-5 relevant hashtags at end
- 1 clear call-to-action (question, link, or comment prompt)
- Authentic, not corporate speak
- No emojis unless {tone} is "casual"

Return JSON: {{"post": "...", "hashtags": [...], "best_posting_time": "..."}}
"""
        }]
    )
    return json.loads(response.content[0].text)

def repurpose_blog_post(blog_url: str, platforms: list) -> dict:
    """Convert a blog post into platform-specific social content."""
    blog_content = fetch_blog_content(blog_url)

    posts = {}
    for platform in platforms:
        char_limits = {"Twitter": 280, "LinkedIn": 3000, "Instagram": 2200}
        response = client.messages.create(
            model="claude-haiku-20240307",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": f"""Repurpose this blog post for {platform}.
Character limit: {char_limits[platform]}
Blog content: {blog_content[:2000]}

For Twitter: Thread of 5-7 tweets, each as bullet points
For LinkedIn: Single narrative post with key insights
For Instagram: Caption with 5 key points, 10-15 hashtags

Return the post text only."""
            }]
        ).content[0].text

        posts[platform] = response

    return posts
```

## Scheduling Automation

### Buffer API Integration

```python
import requests

class BufferScheduler:
    def __init__(self, access_token: str):
        self.token = access_token
        self.base_url = "https://api.bufferapp.com/1"

    def get_optimal_times(self, profile_id: str) -> list:
        """Get Buffer's recommended posting times for your audience."""
        response = requests.get(
            f"{self.base_url}/profiles/{profile_id}/schedules.json",
            params={"access_token": self.token}
        )
        return response.json()

    def schedule_post(self, profile_id: str, text: str, media_url: str = None,
                      scheduled_at: datetime = None) -> dict:
        data = {
            "profile_ids[]": profile_id,
            "text": text,
            "access_token": self.token
        }
        if scheduled_at:
            data["scheduled_at"] = scheduled_at.isoformat()
        else:
            data["now"] = False  # Add to Buffer queue

        if media_url:
            data["media[link]"] = media_url

        return requests.post(f"{self.base_url}/updates/create.json", data=data).json()

    def bulk_schedule_week(self, profile_id: str, posts: list):
        """Schedule a full week of content."""
        results = []
        for post in posts:
            result = self.schedule_post(
                profile_id=profile_id,
                text=post["text"],
                scheduled_at=post["scheduled_at"]
            )
            results.append(result)
            time.sleep(1)  # Rate limiting
        return results
```

## Content Curation Automation

```python
def curate_industry_content(rss_feeds: list, keywords: list) -> list:
    """Auto-curate relevant industry content for sharing."""
    curated = []

    for feed_url in rss_feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:10]:  # Latest 10 per feed
            text = (entry.title + " " + entry.get("summary", "")).lower()

            # Filter by relevance
            if any(kw.lower() in text for kw in keywords):
                curated.append({
                    "title": entry.title,
                    "url": entry.link,
                    "summary": entry.get("summary", "")[:300],
                    "source": feed.feed.title,
                    "published": entry.get("published", ""),
                })

    # Score by engagement potential using AI
    for item in curated:
        item["relevance_score"] = score_content_relevance(item, keywords)

    return sorted(curated, key=lambda x: x["relevance_score"], reverse=True)[:5]
```

## Engagement Monitoring

```python
def monitor_engagement(post_id: str, platform: str) -> dict:
    """Track post performance and trigger response actions."""
    metrics = get_post_metrics(post_id, platform)

    # Respond to comments quickly (within 2 hours is ideal)
    if metrics["comment_count"] > 0:
        new_comments = get_new_comments(post_id, since=metrics["last_checked"])
        for comment in new_comments:
            if needs_response(comment):
                draft_response = generate_comment_response(comment)
                alert_social_manager(post_id, comment, draft_response)

    return metrics

def generate_comment_response(comment: dict) -> str:
    """Draft response to comments for human review."""
    response = client.messages.create(
        model="claude-haiku-20240307",
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": f"""Draft a warm, professional reply to this comment.
Comment: {comment['text']}
Post context: {comment['post_text']}
Brand voice: Professional, helpful, human — not corporate.
Keep under 100 words. Return reply text only."""
        }]
    ).content[0].text
    return response
```

## Analytics and Optimization

```python
SOCIAL_KPI_TARGETS = {
    "LinkedIn": {
        "engagement_rate": 0.03,      # > 3% = good
        "follower_growth_monthly": 0.05,  # 5% MoM
        "post_reach_per_follower": 0.3,   # Reach 30% of followers per post
    },
    "Twitter": {
        "engagement_rate": 0.01,
        "follower_growth_monthly": 0.03,
        "impressions_per_follower": 2.0,
    }
}

def generate_performance_report(period: str = "last_30_days") -> dict:
    """Weekly/monthly social performance report."""
    metrics = pull_all_platform_metrics(period)
    top_posts = identify_top_performers(metrics, top_n=5)
    growth_analysis = analyze_follower_growth(period)

    return {
        "summary": metrics,
        "top_performing_posts": top_posts,
        "content_type_breakdown": analyze_by_content_type(metrics),
        "recommendations": generate_recommendations(metrics),
        "follower_growth": growth_analysis
    }
```

## Posting Frequency Guide

| Platform | Optimal Frequency | Best Times (Local) |
|----------|------------------|--------------------|
| LinkedIn | 3-5x per week | Tue-Thu, 8-10am, 12-1pm |
| Twitter/X | 3-7x per day | 8-10am, 12-1pm, 5-6pm |
| Instagram | 4-7x per week | Tue-Fri, 11am, 1pm, 7pm |
| Facebook | 3-5x per week | 1-4pm, Wed-Thu |
| YouTube | 1-2x per week | Fri-Sun, 12-4pm |
