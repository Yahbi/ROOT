"""Content Network — 15 content creation and distribution agents."""

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
    AgentProfile(
        id="seo_optimizer", name="SEO Optimizer",
        role="SEO Optimization", tier=2, connector_type="internal",
        description="Optimizes content, site structure, and technical SEO for maximum organic search visibility",
        capabilities=[
            _cap("seo", "Audit on-page, off-page, and technical SEO factors"),
            _cap("web_search", "Research keyword opportunities, SERPs, and competitor rankings"),
            _cap("content_marketing", "Align content strategy with search intent and topical authority"),
            _cap("data_analysis", "Analyze organic traffic trends and ranking distributions"),
            _cap("benchmark_analysis", "Track SEO performance against domain authority benchmarks"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="social_media_manager", name="Social Media Manager",
        role="Social Media Management", tier=2, connector_type="internal",
        description="Manages social media presence, scheduling, engagement, and growth across platforms",
        capabilities=[
            _cap("social_media", "Plan and schedule content across multiple social platforms"),
            _cap("writing", "Craft platform-native captions, threads, and engagement copy"),
            _cap("data_analysis", "Analyze engagement, reach, and follower growth metrics"),
            _cap("web_search", "Monitor brand mentions, trending topics, and competitors"),
            _cap("content_marketing", "Integrate social distribution into content campaigns"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="case_study_writer", name="Case Study Writer",
        role="Case Study Creation", tier=2, connector_type="internal",
        description="Produces compelling case studies and success stories that drive trust and conversion",
        capabilities=[
            _cap("writing", "Write structured case studies with problem, solution, and results"),
            _cap("research", "Gather metrics, testimonials, and implementation details"),
            _cap("content_marketing", "Position case studies within the sales and marketing funnel"),
            _cap("seo", "Optimize case study pages for relevant buyer-intent keywords"),
            _cap("web_search", "Research industry benchmarks to contextualize results"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="community_manager", name="Community Manager",
        role="Community Management", tier=2, connector_type="internal",
        description="Actively manages online communities, moderates discussions, and drives engagement",
        capabilities=[
            _cap("social_media", "Manage community channels and respond to members"),
            _cap("writing", "Create engaging community posts, polls, and announcements"),
            _cap("data_analysis", "Track community health metrics and engagement rates"),
            _cap("content_marketing", "Drive community growth through content and events"),
            _cap("web_search", "Monitor community sentiment and competitive community strategies"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="podcast_strategist", name="Podcast Strategist",
        role="Podcast Strategy", tier=2, connector_type="internal",
        description="Develops podcast growth strategies, audience development plans, and monetization roadmaps",
        capabilities=[
            _cap("content_marketing", "Design podcast growth funnels and listener acquisition strategies"),
            _cap("market_research", "Research podcast niche saturation and audience demand"),
            _cap("web_search", "Track podcast industry trends, platforms, and monetization models"),
            _cap("data_analysis", "Analyze listener retention, episode performance, and drop-off points"),
            _cap("revenue_optimization", "Develop sponsorship, membership, and premium content strategies"),
        ],
        metadata={"priority": 2},
    ),
]
