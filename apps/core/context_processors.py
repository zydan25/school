from django.conf import settings


def platform_context(request):
    return {
        "school_context": getattr(request, "school", None),
        "school_membership": getattr(request, "school_membership", None),
        "platform_name": "سكول",
        "platform_language": settings.LANGUAGE_CODE,
    }
