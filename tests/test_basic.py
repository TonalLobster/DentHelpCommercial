def test_home_page(client):
    """Test that the home page loads successfully."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'DentHelp AI' in response.data


def test_login_page(client):
    """Test that the login page loads successfully."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Logga in' in response.data


def test_login_logout(client, auth):
    """Test login and logout functionality."""
    # Test login
    response = auth.login()
    assert response.status_code in (200, 302)  # Success or redirect
    
    # Check that we can access a protected page
    response = client.get('/dashboard')
    assert response.status_code in (200, 302)  # Success or redirect
    
    # Test logout
    response = auth.logout()
    assert response.status_code in (200, 302)  # Success or redirect
    
    # Check that we can't access protected page after logout
    response = client.get('/dashboard', follow_redirects=True)
    assert b'Logga in' in response.data