from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from django.core.exceptions import MultipleObjectsReturned


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to fix MultipleObjectsReturned error when multiple
    SocialApp entries exist for the same provider.
    """
    
    def get_app(self, request, provider, client_id=None):
        """
        Override to handle MultipleObjectsReturned error by using filter().first()
        instead of get().
        """
        try:
            # Try the default method first
            return super().get_app(request, provider, client_id=client_id)
        except MultipleObjectsReturned:
            # If MultipleObjectsReturned, use filter().first() instead
            current_site = Site.objects.get_current()
            
            # Try to get app for current site
            apps = SocialApp.objects.filter(
                provider=provider,
                sites__id=current_site.id
            ).distinct()
            
            if apps.exists():
                return apps.first()
            
            # Fallback: get any app for this provider
            apps = SocialApp.objects.filter(provider=provider).distinct()
            if apps.exists():
                app = apps.first()
                # Ensure it's associated with current site
                if current_site not in app.sites.all():
                    app.sites.add(current_site)
                return app
            
            # If no app in DB, try to get from settings
            from allauth.socialaccount import providers
            
            provider_instance = providers.registry.by_id(provider)
            if provider_instance:
                app_config = provider_instance.get_app(request)
                if app_config and app_config.client_id:
                    # Create app from settings if it doesn't exist
                    app = SocialApp.objects.create(
                        provider=provider,
                        name=provider.title(),
                        client_id=app_config.client_id,
                        secret=app_config.secret,
                        key=app_config.key or '',
                    )
                    app.sites.add(current_site)
                    return app
            
            # If still no app, raise the original exception
            raise SocialApp.DoesNotExist(
                f"No SocialApp found for provider '{provider}'"
            )

