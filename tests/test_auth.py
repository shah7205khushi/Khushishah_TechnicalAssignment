def test_login_page_renders(client):
    """Test that login page loads with HTTP 200 and includes Savyant Systems branding."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Savyant Systems" in response.data
    assert b"admin@savyant.com" in response.data


def test_unauthenticated_access_redirects_to_login(client):
    """Unauthenticated access to protected route redirects to login."""
    response = client.get('/orders/', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_invalid_login_fails(client):
    """Submitting wrong password must fail."""
    response = client.post('/login', data={
        'email': 'admin@savyant.com',
        'password': 'WrongPassword123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_admin_login_success(client):
    """Admin logs in successfully and receives admin role in session."""
    response = client.post('/login', data={
        'email': 'admin@savyant.com',
        'password': 'Admin@123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"System Administrator" in response.data
    assert b"Administrator" in response.data

    with client.session_transaction() as sess:
        assert sess['role'] == 'admin'
        assert sess['user_email'] == 'admin@savyant.com'


def test_sales_user_login_success(client):
    """Sales user logs in successfully and receives sales_user role in session."""
    response = client.post('/login', data={
        'email': 'sales@savyant.com',
        'password': 'Sales@123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Sarah Sales" in response.data
    assert b"Sales User" in response.data

    with client.session_transaction() as sess:
        assert sess['role'] == 'sales_user'
        assert sess['user_email'] == 'sales@savyant.com'


def test_logout(client):
    """Logging out clears the session."""
    # First login
    client.post('/login', data={
        'email': 'admin@savyant.com',
        'password': 'Admin@123'
    })
    # Then logout
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"logged out" in response.data

    with client.session_transaction() as sess:
        assert 'user_id' not in sess
def test_admin_route_forbidden_for_sales_user(client):
    """Sales user trying to access admin-only route must be blocked and redirected."""
    # Login as sales user
    client.post('/login', data={
        'email': 'sales@savyant.com',
        'password': 'Sales@123'
    })
    # Attempt to access admin-only report route
    response = client.get('/reports/customer-sales', follow_redirects=True)
    assert response.status_code == 200
    assert b"Access denied: Administrator privileges required" in response.data


def test_admin_route_accessible_for_admin(client):
    """Admin user is permitted to access admin-only routes."""
    # Login as admin
    client.post('/login', data={
        'email': 'admin@savyant.com',
        'password': 'Admin@123'
    })
    # Access admin-only route
    response = client.get('/reports/customer-sales')
    assert response.status_code == 200
    assert b"Customer Sales Report Stub" in response.data
