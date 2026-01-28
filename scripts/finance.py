"""
Financial Dashboard - Track business and personal finance metrics.

Provides:
- Business metrics (MRR, ARR, runway, burn rate)
- Personal finance (net worth, savings rate, investment performance)
- Weekly/monthly financial health snapshots
- Budget tracking and alerts
- Financial goal progress

Data stored in data/financial_metrics.json (private - .gitignore).
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, List

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PRIVATE_DIR = os.path.expanduser("~/.bestupid-private")
FINANCE_DATA_FILE = os.path.join(PRIVATE_DIR, "financial_metrics.json")

# Default budget categories
BUDGET_CATEGORIES = [
    "housing", "food", "transportation", "health", "entertainment",
    "subscriptions", "education", "savings", "investments", "misc"
]


def ensure_directories():
    """Create private directory if needed."""
    if not os.path.exists(PRIVATE_DIR):
        os.makedirs(PRIVATE_DIR)


def load_finance_data() -> dict:
    """Load financial data from file."""
    if os.path.exists(FINANCE_DATA_FILE):
        try:
            with open(FINANCE_DATA_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass

    return {
        "version": "1.0",
        "business": {
            "entries": [],
            "current": {}
        },
        "personal": {
            "entries": [],
            "current": {},
            "goals": []
        },
        "budget": {
            "monthly_limits": {},
            "current_month": {}
        }
    }


def save_finance_data(data: dict):
    """Save financial data to file."""
    ensure_directories()

    data["last_updated"] = datetime.now().isoformat()

    with open(FINANCE_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def log_business_metrics(
    mrr: float = None,
    arr: float = None,
    cash_balance: float = None,
    monthly_burn: float = None,
    customers: int = None,
    churn_rate: float = None,
    notes: str = ""
) -> dict:
    """
    Log business metrics snapshot.

    Args:
        mrr: Monthly Recurring Revenue
        arr: Annual Recurring Revenue
        cash_balance: Current cash in bank
        monthly_burn: Monthly expenses/burn rate
        customers: Number of paying customers
        churn_rate: Monthly churn rate (0-1)
        notes: Optional notes

    Returns:
        Updated metrics dict
    """
    data = load_finance_data()

    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat()
    }

    if mrr is not None:
        entry["mrr"] = mrr
        data["business"]["current"]["mrr"] = mrr

    if arr is not None:
        entry["arr"] = arr
        data["business"]["current"]["arr"] = arr

    if cash_balance is not None:
        entry["cash_balance"] = cash_balance
        data["business"]["current"]["cash_balance"] = cash_balance

    if monthly_burn is not None:
        entry["monthly_burn"] = monthly_burn
        data["business"]["current"]["monthly_burn"] = monthly_burn

    if customers is not None:
        entry["customers"] = customers
        data["business"]["current"]["customers"] = customers

    if churn_rate is not None:
        entry["churn_rate"] = churn_rate
        data["business"]["current"]["churn_rate"] = churn_rate

    if notes:
        entry["notes"] = notes

    # Calculate runway
    if cash_balance and monthly_burn and monthly_burn > 0:
        runway_months = cash_balance / monthly_burn
        entry["runway_months"] = round(runway_months, 1)
        data["business"]["current"]["runway_months"] = round(runway_months, 1)

    data["business"]["entries"].append(entry)
    save_finance_data(data)

    print(f"Logged business metrics for {entry['date']}")
    return entry


def log_personal_metrics(
    net_worth: float = None,
    liquid_assets: float = None,
    investments: float = None,
    debt: float = None,
    monthly_income: float = None,
    monthly_expenses: float = None,
    notes: str = ""
) -> dict:
    """
    Log personal finance snapshot.

    Args:
        net_worth: Total net worth
        liquid_assets: Cash and easily accessible funds
        investments: Investment account balances
        debt: Total debt
        monthly_income: Monthly income (after tax)
        monthly_expenses: Monthly expenses
        notes: Optional notes

    Returns:
        Updated metrics dict
    """
    data = load_finance_data()

    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat()
    }

    if net_worth is not None:
        entry["net_worth"] = net_worth
        data["personal"]["current"]["net_worth"] = net_worth

    if liquid_assets is not None:
        entry["liquid_assets"] = liquid_assets
        data["personal"]["current"]["liquid_assets"] = liquid_assets

    if investments is not None:
        entry["investments"] = investments
        data["personal"]["current"]["investments"] = investments

    if debt is not None:
        entry["debt"] = debt
        data["personal"]["current"]["debt"] = debt

    if monthly_income is not None:
        entry["monthly_income"] = monthly_income
        data["personal"]["current"]["monthly_income"] = monthly_income

    if monthly_expenses is not None:
        entry["monthly_expenses"] = monthly_expenses
        data["personal"]["current"]["monthly_expenses"] = monthly_expenses

    # Calculate savings rate
    if monthly_income and monthly_expenses:
        savings = monthly_income - monthly_expenses
        savings_rate = savings / monthly_income if monthly_income > 0 else 0
        entry["savings_rate"] = round(savings_rate, 3)
        data["personal"]["current"]["savings_rate"] = round(savings_rate, 3)

    # Calculate months of runway (personal)
    if liquid_assets and monthly_expenses and monthly_expenses > 0:
        personal_runway = liquid_assets / monthly_expenses
        entry["personal_runway_months"] = round(personal_runway, 1)
        data["personal"]["current"]["personal_runway_months"] = round(personal_runway, 1)

    if notes:
        entry["notes"] = notes

    data["personal"]["entries"].append(entry)
    save_finance_data(data)

    print(f"Logged personal metrics for {entry['date']}")
    return entry


def set_financial_goal(
    name: str,
    target_amount: float,
    current_amount: float = 0,
    deadline: str = None,
    category: str = "savings"
) -> dict:
    """
    Set or update a financial goal.

    Args:
        name: Goal name
        target_amount: Target amount to reach
        current_amount: Current progress
        deadline: Target date (YYYY-MM-DD)
        category: Goal category

    Returns:
        Goal dict
    """
    data = load_finance_data()

    # Find existing goal or create new
    goals = data["personal"].get("goals", [])
    existing = next((g for g in goals if g["name"] == name), None)

    goal = {
        "name": name,
        "target_amount": target_amount,
        "current_amount": current_amount,
        "deadline": deadline,
        "category": category,
        "progress": round(current_amount / target_amount, 3) if target_amount > 0 else 0,
        "updated_at": datetime.now().isoformat()
    }

    if deadline:
        try:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d")
            days_remaining = (deadline_date - datetime.now()).days
            goal["days_remaining"] = days_remaining

            # Calculate required monthly savings
            if days_remaining > 0:
                remaining_amount = target_amount - current_amount
                months_remaining = days_remaining / 30
                goal["monthly_needed"] = round(remaining_amount / months_remaining, 2)
        except ValueError:
            pass

    if existing:
        goals.remove(existing)

    goals.append(goal)
    data["personal"]["goals"] = goals
    save_finance_data(data)

    print(f"Set goal: {name} - ${current_amount:,.0f} / ${target_amount:,.0f} ({goal['progress']*100:.1f}%)")
    return goal


def log_expense(amount: float, category: str, description: str = "") -> dict:
    """
    Log an expense for budget tracking.

    Args:
        amount: Expense amount
        category: Budget category
        description: Optional description

    Returns:
        Updated budget status
    """
    data = load_finance_data()

    now = datetime.now()
    month_key = now.strftime("%Y-%m")

    if "budget" not in data:
        data["budget"] = {"monthly_limits": {}, "months": {}}

    if "months" not in data["budget"]:
        data["budget"]["months"] = {}

    if month_key not in data["budget"]["months"]:
        data["budget"]["months"][month_key] = {"expenses": [], "totals": {}}

    expense = {
        "date": now.strftime("%Y-%m-%d"),
        "amount": amount,
        "category": category,
        "description": description
    }

    data["budget"]["months"][month_key]["expenses"].append(expense)

    # Update totals
    totals = data["budget"]["months"][month_key]["totals"]
    totals[category] = totals.get(category, 0) + amount
    totals["_total"] = totals.get("_total", 0) + amount

    save_finance_data(data)

    print(f"Logged ${amount:.2f} in {category}")
    return expense


def get_budget_status() -> dict:
    """
    Get current month's budget status.

    Returns:
        dict with spending by category and remaining budget
    """
    data = load_finance_data()

    now = datetime.now()
    month_key = now.strftime("%Y-%m")

    limits = data.get("budget", {}).get("monthly_limits", {})
    current = data.get("budget", {}).get("months", {}).get(month_key, {})
    totals = current.get("totals", {})

    status = {
        "month": month_key,
        "days_remaining": (datetime(now.year, now.month + 1, 1) - now).days if now.month < 12
                          else (datetime(now.year + 1, 1, 1) - now).days,
        "categories": {},
        "total_spent": totals.get("_total", 0),
        "over_budget": []
    }

    for category in BUDGET_CATEGORIES:
        spent = totals.get(category, 0)
        limit = limits.get(category, 0)

        status["categories"][category] = {
            "spent": spent,
            "limit": limit,
            "remaining": limit - spent if limit > 0 else None,
            "percent_used": round(spent / limit * 100, 1) if limit > 0 else None
        }

        if limit > 0 and spent > limit:
            status["over_budget"].append({
                "category": category,
                "over_by": spent - limit
            })

    return status


def calculate_trends(entries: List[dict], metric: str, periods: int = 6) -> dict:
    """
    Calculate trends for a metric over time.

    Args:
        entries: List of metric entries
        metric: Metric name to analyze
        periods: Number of periods to analyze

    Returns:
        dict with trend analysis
    """
    recent = entries[-periods:] if len(entries) >= periods else entries

    values = [e.get(metric) for e in recent if e.get(metric) is not None]

    if len(values) < 2:
        return {"trend": "insufficient_data"}

    change = values[-1] - values[0]
    percent_change = (change / values[0] * 100) if values[0] != 0 else 0

    return {
        "current": values[-1],
        "previous": values[-2],
        "change": round(change, 2),
        "percent_change": round(percent_change, 1),
        "trend": "up" if change > 0 else "down" if change < 0 else "flat",
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 2)
    }


def get_financial_summary() -> dict:
    """
    Get complete financial summary for dashboard.

    Returns:
        dict with business, personal, budget, and goals data
    """
    data = load_finance_data()

    business = data.get("business", {})
    personal = data.get("personal", {})

    # Business trends
    business_trends = {}
    if business.get("entries"):
        for metric in ["mrr", "arr", "runway_months", "customers"]:
            business_trends[metric] = calculate_trends(business["entries"], metric)

    # Personal trends
    personal_trends = {}
    if personal.get("entries"):
        for metric in ["net_worth", "savings_rate", "investments"]:
            personal_trends[metric] = calculate_trends(personal["entries"], metric)

    # Goals progress
    goals = personal.get("goals", [])
    active_goals = [g for g in goals if g.get("progress", 0) < 1]

    return {
        "business": {
            "current": business.get("current", {}),
            "trends": business_trends
        },
        "personal": {
            "current": personal.get("current", {}),
            "trends": personal_trends
        },
        "budget": get_budget_status(),
        "goals": {
            "total": len(goals),
            "active": len(active_goals),
            "details": active_goals
        }
    }


def generate_finance_nudges() -> List[str]:
    """Generate finance-related nudges for daily briefing."""
    nudges = []
    data = load_finance_data()

    # Runway warning
    business = data.get("business", {}).get("current", {})
    if business.get("runway_months") and business["runway_months"] < 6:
        nudges.append(f"Business runway: {business['runway_months']:.1f} months - consider fundraising")

    # Savings rate warning
    personal = data.get("personal", {}).get("current", {})
    if personal.get("savings_rate") and personal["savings_rate"] < 0.1:
        nudges.append(f"Savings rate at {personal['savings_rate']*100:.0f}% - below 10% target")

    # Budget alerts
    budget = get_budget_status()
    for over in budget.get("over_budget", [])[:2]:
        nudges.append(f"Over budget in {over['category']}: ${over['over_by']:.0f}")

    # Goal reminders
    for goal in data.get("personal", {}).get("goals", []):
        if goal.get("days_remaining") and goal["days_remaining"] < 30 and goal.get("progress", 0) < 0.9:
            nudges.append(f"Goal '{goal['name']}' deadline in {goal['days_remaining']} days - {goal['progress']*100:.0f}% complete")

    return nudges


def format_summary_for_display() -> str:
    """Format financial summary as readable text."""
    summary = get_financial_summary()
    lines = []

    lines.append("=== Financial Dashboard ===\n")

    # Business
    biz = summary.get("business", {}).get("current", {})
    if biz:
        lines.append("BUSINESS")
        if biz.get("mrr"):
            lines.append(f"  MRR: ${biz['mrr']:,.0f}")
        if biz.get("runway_months"):
            lines.append(f"  Runway: {biz['runway_months']:.1f} months")
        if biz.get("customers"):
            lines.append(f"  Customers: {biz['customers']}")
        lines.append("")

    # Personal
    pers = summary.get("personal", {}).get("current", {})
    if pers:
        lines.append("PERSONAL")
        if pers.get("net_worth"):
            lines.append(f"  Net Worth: ${pers['net_worth']:,.0f}")
        if pers.get("savings_rate"):
            lines.append(f"  Savings Rate: {pers['savings_rate']*100:.1f}%")
        if pers.get("personal_runway_months"):
            lines.append(f"  Personal Runway: {pers['personal_runway_months']:.1f} months")
        lines.append("")

    # Goals
    goals = summary.get("goals", {})
    if goals.get("details"):
        lines.append("ACTIVE GOALS")
        for g in goals["details"][:3]:
            lines.append(f"  {g['name']}: {g['progress']*100:.0f}% (${g['current_amount']:,.0f}/${g['target_amount']:,.0f})")
        lines.append("")

    # Nudges
    nudges = generate_finance_nudges()
    if nudges:
        lines.append("ALERTS")
        for n in nudges:
            lines.append(f"  ! {n}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    ensure_directories()

    if len(sys.argv) < 2:
        print(format_summary_for_display())

    elif sys.argv[1] == "business":
        # Interactive business metrics logging
        print("\nLog Business Metrics")
        mrr = input("MRR ($): ").strip()
        cash = input("Cash Balance ($): ").strip()
        burn = input("Monthly Burn ($): ").strip()
        customers = input("Customers: ").strip()

        log_business_metrics(
            mrr=float(mrr) if mrr else None,
            cash_balance=float(cash) if cash else None,
            monthly_burn=float(burn) if burn else None,
            customers=int(customers) if customers else None
        )

    elif sys.argv[1] == "personal":
        # Interactive personal metrics logging
        print("\nLog Personal Metrics")
        nw = input("Net Worth ($): ").strip()
        liquid = input("Liquid Assets ($): ").strip()
        invest = input("Investments ($): ").strip()
        income = input("Monthly Income ($): ").strip()
        expenses = input("Monthly Expenses ($): ").strip()

        log_personal_metrics(
            net_worth=float(nw) if nw else None,
            liquid_assets=float(liquid) if liquid else None,
            investments=float(invest) if invest else None,
            monthly_income=float(income) if income else None,
            monthly_expenses=float(expenses) if expenses else None
        )

    elif sys.argv[1] == "goal" and len(sys.argv) >= 4:
        name = sys.argv[2]
        target = float(sys.argv[3])
        current = float(sys.argv[4]) if len(sys.argv) > 4 else 0
        deadline = sys.argv[5] if len(sys.argv) > 5 else None
        set_financial_goal(name, target, current, deadline)

    elif sys.argv[1] == "nudges":
        nudges = generate_finance_nudges()
        print("\n=== Finance Nudges ===")
        for nudge in nudges:
            print(f"  - {nudge}")
