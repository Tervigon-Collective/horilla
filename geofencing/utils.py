"""
Geofencing utilities for clock in/out validation.
"""
from geopy.distance import geodesic

from geofencing.models import GeoFencing


def get_company_geofencing(request):
    """
    Return the GeoFencing instance for the current user's company, or None
    if no company, no geofencing record, or geofencing is disabled.
    """
    try:
        company = request.user.employee_get.get_company()
    except Exception:
        return None
    if not company:
        return None
    try:
        geo = GeoFencing.objects.get(company_id=company)
    except GeoFencing.DoesNotExist:
        return None
    if not geo.start:
        return None
    return geo


def validate_request_location(request, get_data=None):
    """
    Validate that the request includes latitude/longitude and that the location
    is inside the company geofence (if geofencing is enabled).

    get_data: callable that takes request and returns a dict-like for lat/long.
              Default is lambda r: {**r.GET, **getattr(r, 'data', {})} for both
              GET (web) and request.data (API).

    Returns:
        (True, None) if geofencing is disabled or user is inside the geofence.
        (False, error_message) if geofencing is enabled and validation fails.
    """
    geo = get_company_geofencing(request)
    if not geo:
        return True, None

    if get_data is None:
        data = getattr(request, "data", None) or request.GET
    else:
        data = get_data(request)

    try:
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is not None and lon is not None:
            lat = float(lat)
            lon = float(lon)
        else:
            return False, "latitude and longitude are required when geofencing is enabled"
    except (TypeError, ValueError):
        return False, "latitude and longitude must be valid numbers"

    geofence_center = (geo.latitude, geo.longitude)
    employee_location = (lat, lon)
    distance = geodesic(geofence_center, employee_location).meters
    if distance <= geo.radius_in_meters:
        return True, None
    return False, "Outside the geofence. You must be within the allowed area to clock in/out."
