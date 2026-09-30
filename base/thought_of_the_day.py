"""
Static Thought of the Day pools and weekday selection.

Mon–Sat: one team pool per weekday. Sunday: hide widget.
Creators list is split odd → Video (Tue), even → Design (Wed).
"""

from datetime import date

# Creators (design & video) — odd indices = Video, even = Design
_CREATORS = [
    "The first cut is never the final story.",
    "White space is doing work even when it looks empty.",
    "Your worst edit today is still better than the one you didn't ship.",
    "Clients buy clarity, not decoration.",
    "Kerning is invisible until it's wrong.",
    "Every frame is a chance to earn the next second of attention.",
    "Steal like an artist; credit like a professional.",
    "The brief is a starting line, not a cage.",
    "Templates get you started; taste gets you hired.",
    "Render times are a good excuse to stretch.",
    "Consistency in a brand beats brilliance in one asset.",
    "Kill your favorite frame if the story doesn't need it.",
    "Good design is invisible; great design is unforgettable.",
    "Feedback is data, not a verdict.",
    "Ship the rough cut before you polish the wrong thing.",
    "Color sets the mood before a single word is read.",
    "The client can't see the 40 hours; make them feel the 40 hours.",
    "Constraints are where creativity actually lives.",
    "Save iterations; future-you will thank present-you.",
    "A great thumbnail is half the view count.",
]

THOUGHTS = {
    "it": [
        "Ship it, then improve it — perfect never deploys.",
        "The bug you ignore today becomes the outage tomorrow.",
        "Automate the thing you've done manually three times.",
        "Documentation is a love letter to your future team.",
        "Uptime is a promise; treat it like one.",
        "Simple systems fail in simple ways.",
        "Back up before you're grateful you did.",
        "The best code is the code you didn't have to write.",
        "Every dependency is a bet on someone else's diligence.",
        "Latency is a tax the customer pays in patience.",
        "Name things well; you'll read them a hundred more times.",
        "Security is a habit, not a feature.",
        "Test in staging so you don't debug in production.",
        "Tech debt is a loan with brutal interest.",
        "The stack matters less than the problem it solves.",
        "Logs are only useful before you need them.",
        "Refactor when it's cheap, not when it's on fire.",
        "A five-minute script can save a five-hour week.",
        "Downtime is measured in trust, not just minutes.",
        "Build for the load you'll have, not the load you have.",
    ],
    "video": [_CREATORS[i] for i in range(len(_CREATORS)) if i % 2 == 1],
    "design": [_CREATORS[i] for i in range(len(_CREATORS)) if i % 2 == 0],
    "marketing": [
        "Nobody wakes up wanting your product; they wake up wanting a result.",
        "Test the headline before you fall in love with it.",
        "Your best campaign is the one you actually measure.",
        "Speak to one person, not an audience.",
        "A boosted post is not a strategy.",
        "Attention is rented, never owned — pay the rent daily.",
        "The hook decides whether the rest of your work gets seen.",
        "Data tells you what; talking to customers tells you why.",
        "If everyone is your customer, no one is.",
        "Vanity metrics feel good; conversion pays rent.",
        "Copy that tries to sound clever usually forgets to sell.",
        "The offer matters more than the ad.",
        "Retention is cheaper than acquisition — nurture what you have.",
        "Trends fade; positioning compounds.",
        "Show, don't claim.",
        "A/B test your assumptions, not just your buttons.",
        "The follow-up email out-earns the launch email.",
        "Clarity converts; cleverness confuses.",
        "Your funnel leaks where you stopped paying attention.",
        "Brand is what people say about you when the ad stops running.",
    ],
    "ecommerce": [
        "Every extra click is a customer you're asking to leave.",
        "The product page is your best salesperson — dress it accordingly.",
        "Reviews are the new storefront window.",
        "Fast shipping forgives a lot; slow shipping forgives nothing.",
        "A confused customer never buys.",
        "Your cart abandonment rate is a conversation you're not having.",
        "Margins are made in operations, not just in pricing.",
        "Repeat buyers are built at unboxing, not at checkout.",
        "Free returns cost less than a bad reputation.",
        "The homepage is a hallway, not a destination.",
        "Photograph the product the way the customer will actually use it.",
        "Scarcity works until it feels like a trick.",
        "One clear CTA beats five competing ones.",
        "Loyalty is earned in the second purchase, not the first.",
        "Your best growth channel is a product worth talking about.",
        "Bundle value, not just discounts.",
        "Speed is a feature customers feel before they name it.",
        "Trust badges matter less than a page that loads.",
        "The story on the label sells the thing inside it.",
        "Owned audiences beat rented ones every quarter.",
    ],
    "procurement": [
        "Savings win applause; risk avoided wins the business — and only one of them makes headlines when it fails.",
        "Anyone can cut a price. The real craft is lowering total cost while making the supplier want to keep working with you.",
        "Your leverage is highest the moment before you sign and gone the moment after — spend it wisely.",
        "The supplier's margin isn't your enemy; a supplier with no margin is.",
        "You don't manage spend you can't see — visibility is the first negotiation you win.",
        "A contract protects you on your worst day, not your best — read it for the day you hope never comes.",
        "The second source you set up in calm times is the one that saves you in a crisis.",
        "Procurement stops being a cost center the day it starts being invited early instead of called last.",
        "Every \"urgent\" request is someone else's failure to plan — build the process that absorbs it without passing the panic to your suppliers.",
        "Buy today the way you'll wish you had bought when you read the news in a year.",
    ],
    # Stored for later use; Sunday is a holiday so these are not shown in the weekly cycle.
    "brand": [
        "Momentum is built in the boring, repeatable days.",
        "The work you're avoiding is usually the work that matters.",
        "Done and out beats perfect and hidden.",
        "Your competitors can copy your product, not your consistency.",
        "Small brands win on speed and specificity.",
        "Reputation is built in years and lost in one bad reply.",
        "Say no to the client who costs you your other clients.",
        "Charge for the value, not the hours.",
        "Cash flow is oxygen; profit is muscle.",
        "The compliment that converts is a customer telling a friend.",
        "Systems scale; heroics don't.",
        "Under-promise the timeline, over-deliver the work.",
        "Your niche is your moat — dig it deeper.",
        "Reply faster than expected; it feels like magic.",
        "Reinvest before you reward yourself.",
        "The follow-up separates pros from hobbyists.",
        "Make one customer wildly happy before chasing a hundred.",
        "Show up when it's slow so you're ready when it's busy.",
        "A brand is a promise repeated until it's believed.",
        "Build something today your future customers will thank you for.",
    ],
}

# weekday(): Monday=0 … Sunday=6
_WEEKDAY_MAP = {
    0: ("IT", "it"),
    1: ("Video", "video"),
    2: ("Design", "design"),
    3: ("Marketing", "marketing"),
    4: ("E-commerce", "ecommerce"),
    5: ("Procurement", "procurement"),
}


def get_thought_of_the_day(for_date: date | None = None) -> dict:
    """
    Return the Thought of the Day for ``for_date`` (defaults to today).

    Sunday → ``{"show": False}``.
    Mon–Sat → ``{"show": True, "team": ..., "thought": ..., "date": ...}``.
    """
    today = for_date or date.today()
    weekday = today.weekday()

    if weekday == 6:  # Sunday
        return {"show": False}

    team_label, pool_key = _WEEKDAY_MAP[weekday]
    pool = THOUGHTS[pool_key]
    thought = pool[today.toordinal() % len(pool)]

    return {
        "show": True,
        "team": team_label,
        "thought": thought,
        "date": today.isoformat(),
    }
