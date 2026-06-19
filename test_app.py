"""
Comprehensive test script for Personal Finance Tracker.
Tests signup, login, CRUD for expenses, and budget operations.
Uses dynamic IDs so tests work on any database state.
"""

import http.cookiejar
import urllib.request
import urllib.parse
import re

BASE = "http://127.0.0.1:8000"

# Setup a cookie-aware opener (to track session cookies / JWT)
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj),
    urllib.request.HTTPRedirectHandler()
)

test_email = "testuser_debug@example.com"
test_password = "TestPass123"
test_name = "Debug User"

passed = 0
failed = 0
errors = []
expense_ids = []  # Track created expense IDs dynamically

def test(name, func):
    global passed, failed
    try:
        result = func()
        if result:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name} -- returned False")
            failed += 1
            errors.append(f"{name}: returned False")
    except Exception as e:
        print(f"  [FAIL] {name} -- {type(e).__name__}: {e}")
        failed += 1
        errors.append(f"{name}: {type(e).__name__}: {e}")


def post_form(url, data, follow_redirects=True):
    """POST form data and return response."""
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=encoded)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    resp = opener.open(req)
    return resp


def get_page(url):
    """GET a page and return response."""
    return opener.open(url)


def extract_expense_ids(html):
    """Extract expense IDs from the expenses page HTML."""
    return re.findall(r'update-expense/(\d+)', html)


# ============================================
# TEST SUITE
# ============================================

print("")
print("PERSONAL FINANCE TRACKER -- DEBUG TEST SUITE")
print("")
print("=" * 50)

# -- 1. Home redirect --
print("")
print("1. Home Page Redirect")
test("GET / redirects to /login", lambda: (
    get_page(f"{BASE}/").url.endswith("/login")
))

# -- 2. Signup page --
print("")
print("2. Signup Page")
test("GET /signup returns 200", lambda: (
    get_page(f"{BASE}/signup").status == 200
))

# -- 3. Signup flow --
print("")
print("3. Signup Flow")
def test_signup():
    resp = post_form(f"{BASE}/signup", {
        "name": test_name,
        "email": test_email,
        "password": test_password
    })
    return resp.url.endswith("/login") or resp.status == 200

test("POST /signup creates user", test_signup)

# Test duplicate email
def test_duplicate_signup():
    resp = post_form(f"{BASE}/signup", {
        "name": test_name,
        "email": test_email,
        "password": test_password
    })
    html = resp.read().decode()
    return "Email already exists" in html

test("POST /signup duplicate email shows error", test_duplicate_signup)

# -- 4. Login page --
print("")
print("4. Login Page")
test("GET /login returns 200", lambda: (
    get_page(f"{BASE}/login").status == 200
))

# -- 5. Invalid login shows error --
print("")
print("5. Invalid Login (error display)")
def test_wrong_password_shows_error():
    resp = post_form(f"{BASE}/login", {
        "email": test_email,
        "password": "wrongpassword"
    })
    html = resp.read().decode()
    return "Invalid email or password" in html

test("Wrong password shows error message", test_wrong_password_shows_error)

def test_nonexistent_user_shows_error():
    resp = post_form(f"{BASE}/login", {
        "email": "nobody@example.com",
        "password": "whatever"
    })
    html = resp.read().decode()
    return "Invalid email or password" in html

test("Nonexistent user shows error message", test_nonexistent_user_shows_error)

# -- 6. Login flow --
print("")
print("6. Login Flow")
def test_login():
    resp = post_form(f"{BASE}/login", {
        "email": test_email,
        "password": test_password
    })
    return resp.url.endswith("/dashboard") or "/dashboard" in resp.url

test("POST /login with valid credentials", test_login)

# Check cookie was set
def test_cookie():
    cookies = list(cj)
    cookie_names = [c.name for c in cookies]
    return "access_token" in cookie_names

test("Login sets access_token cookie", test_cookie)

# -- 7. Dashboard --
print("")
print("7. Dashboard (Authenticated)")
def test_dashboard():
    resp = get_page(f"{BASE}/dashboard")
    html = resp.read().decode()
    return (resp.status == 200 and 
            "Dashboard" in html and
            test_name in html)

test("GET /dashboard shows user name", test_dashboard)

# -- 8. Create Expense --
print("")
print("8. Create Expense")
def test_create_expense_page():
    resp = get_page(f"{BASE}/create-expense")
    return resp.status == 200

test("GET /create-expense returns 200", test_create_expense_page)

def test_create_expense():
    resp = post_form(f"{BASE}/create-expense", {
        "title": "Test Coffee",
        "amount": "150.50",
        "category": "Food",
        "description": "Morning coffee",
        "date": "2026-06-19"
    })
    return resp.url.endswith("/dashboard") or "/dashboard" in resp.url

test("POST /create-expense creates expense", test_create_expense)

# Create a second expense
def test_create_expense2():
    resp = post_form(f"{BASE}/create-expense", {
        "title": "Bus Ticket",
        "amount": "50.00",
        "category": "Transport",
        "description": "Daily commute",
        "date": "2026-06-18"
    })
    return resp.url.endswith("/dashboard") or "/dashboard" in resp.url

test("POST /create-expense second expense", test_create_expense2)

# Create expense without description (testing optional field)
def test_create_expense_no_desc():
    resp = post_form(f"{BASE}/create-expense", {
        "title": "Gym Membership",
        "amount": "500.00",
        "category": "Health",
        "description": "",
        "date": "2026-06-17"
    })
    return resp.url.endswith("/dashboard") or "/dashboard" in resp.url

test("POST /create-expense without description (optional field)", test_create_expense_no_desc)

# -- 9. Expenses List --
print("")
print("9. Expenses List")
def test_expenses_list():
    resp = get_page(f"{BASE}/expenses")
    html = resp.read().decode()
    ids = extract_expense_ids(html)
    expense_ids.clear()
    expense_ids.extend(ids)
    return (resp.status == 200 and 
            "Test Coffee" in html and
            "Bus Ticket" in html and
            "Gym Membership" in html and
            len(ids) >= 3)

test("GET /expenses lists all expenses", test_expenses_list)

# -- 10. Update Expense --
print("")
print("10. Update Expense")
def test_update_expense_page():
    if not expense_ids:
        return False
    eid = expense_ids[0]
    resp = get_page(f"{BASE}/update-expense/{eid}")
    html = resp.read().decode()
    return resp.status == 200 and "update-expense" in html.lower()

test("GET /update-expense page returns 200", test_update_expense_page)

def test_update_expense():
    if not expense_ids:
        return False
    eid = expense_ids[0]
    resp = post_form(f"{BASE}/update-expense/{eid}", {
        "title": "Updated Coffee",
        "amount": "200.00",
        "category": "Food",
        "description": "Updated description",
        "date": "2026-06-19"
    })
    return resp.url.endswith("/dashboard") or "/dashboard" in resp.url

test("POST /update-expense updates expense", test_update_expense)

# Verify update
def test_verify_update():
    resp = get_page(f"{BASE}/expenses")
    html = resp.read().decode()
    return "Updated Coffee" in html and "200.00" in html

test("Updated expense appears in list", test_verify_update)

# -- 11. Budget --
print("")
print("11. Budget")
def test_budget_page():
    resp = get_page(f"{BASE}/budget")
    return resp.status == 200

test("GET /budget returns 200", test_budget_page)

def test_set_budget():
    resp = post_form(f"{BASE}/budget", {
        "monthly_limit": "5000.00"
    })
    return resp.url.endswith("/dashboard") or "/dashboard" in resp.url

test("POST /budget sets budget", test_set_budget)

# Verify budget on dashboard
def test_verify_budget():
    resp = get_page(f"{BASE}/dashboard")
    html = resp.read().decode()
    return "5000.00" in html

test("Budget appears on dashboard", test_verify_budget)

# Update budget
def test_update_budget():
    resp = post_form(f"{BASE}/budget", {
        "monthly_limit": "10000.00"
    })
    return resp.url.endswith("/dashboard") or "/dashboard" in resp.url

test("POST /budget updates existing budget", test_update_budget)

# -- 12. Dashboard Stats --
print("")
print("12. Dashboard Stats Verification")
def test_dashboard_stats():
    resp = get_page(f"{BASE}/dashboard")
    html = resp.read().decode()
    # Updated Coffee = 200, Bus Ticket = 50, Gym = 500 => total = 750
    has_total = "750.00" in html
    has_budget = "10000.00" in html
    has_remaining = "9250.00" in html
    return has_total and has_budget and has_remaining

test("Dashboard shows correct totals", test_dashboard_stats)

# -- 13. Delete Expense --
print("")
print("13. Delete Expense")
def test_delete_expense():
    if len(expense_ids) < 2:
        return False
    eid = expense_ids[1]  # Delete "Bus Ticket"
    resp = get_page(f"{BASE}/delete-expense/{eid}")
    return resp.url.endswith("/dashboard") or "/dashboard" in resp.url

test("GET /delete-expense deletes and redirects", test_delete_expense)

def test_verify_delete():
    resp = get_page(f"{BASE}/expenses")
    html = resp.read().decode()
    return "Bus Ticket" not in html and "Updated Coffee" in html

test("Deleted expense no longer in list", test_verify_delete)

# -- 14. Auth Protection --
print("")
print("14. Auth Protection")

# Create a fresh opener without cookies
cj_no_auth = http.cookiejar.CookieJar()
opener_no_auth = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj_no_auth),
    urllib.request.HTTPRedirectHandler()
)

def test_dashboard_no_auth():
    resp = opener_no_auth.open(f"{BASE}/dashboard")
    return resp.url.endswith("/login") or "/login" in resp.url

test("Dashboard redirects to login without auth", test_dashboard_no_auth)

def test_expenses_no_auth():
    resp = opener_no_auth.open(f"{BASE}/expenses")
    return resp.url.endswith("/login") or "/login" in resp.url

test("Expenses redirects to login without auth", test_expenses_no_auth)

def test_create_expense_no_auth():
    resp = opener_no_auth.open(f"{BASE}/create-expense")
    return resp.url.endswith("/login") or "/login" in resp.url

test("Create-expense redirects without auth", test_create_expense_no_auth)

def test_budget_no_auth():
    resp = opener_no_auth.open(f"{BASE}/budget")
    return resp.url.endswith("/login") or "/login" in resp.url

test("Budget redirects without auth", test_budget_no_auth)

# -- 15. Logout --
print("")
print("15. Logout")
def test_logout():
    resp = get_page(f"{BASE}/logout")
    return resp.url.endswith("/login") or "/login" in resp.url

test("GET /logout redirects to login", test_logout)

def test_after_logout():
    resp = get_page(f"{BASE}/dashboard")
    return resp.url.endswith("/login") or "/login" in resp.url

test("Dashboard redirects after logout", test_after_logout)


# ============================================
# CLEANUP: Delete test data
# ============================================
print("")
print("Cleanup")

# Login again to clean up
post_form(f"{BASE}/login", {
    "email": test_email,
    "password": test_password
})

# Delete remaining expenses
for eid in expense_ids:
    try:
        get_page(f"{BASE}/delete-expense/{eid}")
    except:
        pass

print("  Cleaned up test expenses")

# ============================================
# RESULTS
# ============================================
print("")
print("=" * 50)
print(f"")
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("")

if errors:
    print("FAILURES:")
    for err in errors:
        print(f"   - {err}")
    print()

if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print(f"{failed} test(s) failed. See details above.")
print("")
