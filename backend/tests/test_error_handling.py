import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.test_client() as client:
        yield client

def test_traceback_hidden_in_production(client):
    import os
    os.environ["FLASK_ENV"] = "production"
    
    # Trigger an error (e.g. unhandled route that raises Exception, or bad DB call)
    # We can use a mock endpoint or trigger an error by sending bad data to a route
    # Let's hit a route that causes a 404 or something, wait we need a 500 error.
    # We can mock logger.exception to not print to screen.
    # Since we can't easily trigger a 500 without mocking, let's just make sure the error handler exists.
    # Actually, we can test by manually invoking the error handler
    try:
        raise ValueError("Test Error")
    except Exception as e:
        with client.application.test_request_context():
            response, code = client.application.error_handler_spec[None][None][Exception](e)
            assert code == 500
            data = response.get_json()
            assert "traceback" not in data

    os.environ["FLASK_ENV"] = "development"
    try:
        raise ValueError("Test Error")
    except Exception as e:
        with client.application.test_request_context():
            response, code = client.application.error_handler_spec[None][None][Exception](e)
            assert code == 500
            data = response.get_json()
            assert "traceback" in data
