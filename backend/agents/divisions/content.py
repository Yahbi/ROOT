"""Content Network — 10 content creation and distribution agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


CONTENT_ENGINE: list[AgentProfile] = [
    AgentProfile(
        id="article_gen", name="Article Generator",
        role="Article Writing", tier=2, connector_type="internal",
        description="Generates high-quality articles, blog posts, and long-form content",
        capabilities=[
            _cap("article_writing", "Write SEO-optimized articles and blog posts"),
            _cap("seo", "Optimize content for search engine visibility"),
            _cap("web_search", "Research topics and gather source material"),
            _cap("writing", "General-purpose writing and editing"),
            _cap("content_marketing", "Create content aligned with marketing goals"),
        ],
    ),
    AgentProfile(
        id="video_script", name="Video Script Creator",
        role="Video Scripts", tier=2, connector_type="internal",
        description="Creates engaging video scripts for YouTube, TikTok, and social media",
        capabilities=[
            _cap("video_scripting", "Write structured video scripts with hooks and CTAs"),
            _cap("writing", "Craft compelling narratives and dialogue"),
            _cap("web_search", "Research trending topics and competitor videos"),
            _cap("seo", "Optimize titles, descriptions, and tags for discovery"),
        ],
    ),
    AgentProfile(
        id="video_producer", name="Video Production Agent",
        role="Video Production", tier=2, connector_type="internal",
        description="Manages video production workflow from script to publish",
        capabilities=[
            _cap("video_scripting", "Refine scripts for production readiness"),
            _cap("content_marketing", "Align video content with marketing strategy"),
            _cap("social_media", "Optimize videos for platform-specific requirements"),
            _cap("web_search", "Research production techniques and trends"),
        ],
    ),
    AgentProfile(
        id="podcast_creator", name="Podcast Creator",
        role="Podcast Production", tier=2, connector_type="internal",
        description="Creates podcast episodes, show notes, and distribution plans",
        capabilities=[
            _cap("writing", "Write episode scripts and show notes"),
            _cap("web_search", "Research guests and episode topics"),
            _cap("content_marketing", "Promote episodes across channels"),
            _cap("seo", "Optimize show metadata for podcast directories"),
        ],
    ),
    AgentProfile(
        id="course_builder", name="Course Builder",
        role="Course Creation", tier=2, connector_type="internal",
        description="Builds online courses and educational content from concept to launch",
        capabilities=[
            _cap("course_creation", "Design course structure, modules, and assessments"),
            _cap("writing", "Write lesson content and supplementary materials"),
            _cap("web_search", "Research subject matter and competitor courses"),
            _cap("video_scripting", "Script video lessons and tutorials"),
            _cap("content_marketing", "Create landing pages and launch campaigns"),
        ],
    ),
    AgentProfile(
        id="newsletter_agent", name="Newsletter Agent",
        role="Newsletter", tier=2, connector_type="internal",
        description="Creates and manages email newsletters and subscriber growth",
        capabilities=[
            _cap("newsletter_creation", "Write and design email newsletters"),
            _cap("writing", "Craft engaging email copy and subject lines"),
            _cap("web_search", "Curate trending content for newsletters"),
            _cap("data_analysis", "Analyze open rates, CTR, and subscriber metrics"),
            _cap("content_marketing", "Drive subscriber growth and retention"),
        ],
    ),
    AgentProfile(
        id="community_builder", name="Community Builder",
        role="Community", tier=2, connector_type="internal",
        description="Builds and nurtures online communities across platforms",
        capabilities=[
            _cap("social_media", "Manage community channels and engagement"),
            _cap("writing", "Create community content and announcements"),
            _cap("web_search", "Research community-building strategies"),
            _cap("content_marketing", "Drive community growth through content"),
        ],
    ),
    AgentProfile(
        id="publisher", name="Publishing Agent",
        role="Publishing", tier=2, connector_type="internal",
        description="Manages content publishing across platforms and channels",
        capabilities=[
            _cap("content_marketing", "Coordinate cross-platform publishing schedules"),
            _cap("social_media", "Distribute content to social channels"),
            _cap("seo", "Ensure published content is search-optimized"),
            _cap("web_search", "Monitor publishing trends and platform changes"),
        ],
    ),
    AgentProfile(
        id="content_repurposer", name="Content Repurposing Agent",
        role="Content Repurposing", tier=2, connector_type="internal",
        description="Repurposes content across formats (blog to video to tweet to podcast)",
        capabilities=[
            _cap("writing", "Adapt content for different formats and audiences"),
            _cap("video_scripting", "Convert written content into video scripts"),
            _cap("social_media", "Create social media snippets from long-form content"),
            _cap("article_writing", "Expand short-form content into articles"),
            _cap("content_marketing", "Maximize content ROI through repurposing"),
        ],
    ),
    AgentProfile(
        id="audience_analytics", name="Audience Analytics Agent",
        role="Audience Analytics", tier=2, connector_type="internal",
        description="Analyzes audience behavior, demographics, and engagement patterns",
        capabilities=[
            _cap("data_analysis", "Analyze audience metrics and engagement data"),
            _cap("web_search", "Research audience segments and market trends"),
            _cap("content_marketing", "Recommend content strategy based on analytics"),
            _cap("seo", "Identify search intent and keyword opportunities"),
        ],
    ),
]
