import datetime
import base64

import requests

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from apps.crowdfunding import tasks
from apps.crowdfunding.models import Campaign, Transaction
from apps.crowdfunding.forms import DonateNewUserForm, FormDonate, CampaignForm

from shared.shortcuts import log


@login_required
def campaign_create(request):

    if request.method == 'POST':
        campaign_form = CampaignForm(data=request.POST, files=request.FILES)

        if campaign_form.is_valid():
            created_campaign = campaign_form.save()
            created_campaign.owner = request.user
            created_campaign.editors.add(request.user)
            created_campaign.save()
            return redirect('profiles:profile_campaigns')
    else:
        campaign_form = CampaignForm()

    context = {'campaign_form': campaign_form}
    return render(request, 'crowdfunding/campaign_create.html', context)


@login_required
def campaign_edit(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)

    if request.method == 'GET':
        campaign_form = CampaignForm(instance=campaign)
        published = (campaign.state == campaign.STATE_PUBLIC)
        context = {'campaign_form': campaign_form, 'campaign': campaign, 'published': published}
        return render(request, 'crowdfunding/campaign_edit.html', context)

    elif request.method == 'POST':
        if request.POST.get("delete", False):
            campaign.delete()
        else:
            # Save edited
            campaign_form = CampaignForm(instance=campaign, data=request.POST, files=request.FILES)

            if campaign_form.is_valid():
                # Publish if needed
                if request.POST.get("publish", False):
                    campaign.state = campaign.STATE_PUBLIC
                    start = timezone.now()
                    campaign.date_start = start
                    finish = start + datetime.timedelta(days=campaign.duration)
                    campaign.date_finish = finish
                    tasks.finish_campaign.apply_async((campaign.id,), eta=finish)
                campaign_form.save()

        return redirect('profiles:profile_campaigns')


def campaigns_public(request):
    campaigns = Campaign.objects.exclude(state=Campaign.STATE_DRAFT)
    context = {'campaigns': campaigns}
    return render(request, 'crowdfunding/campaigns_public.html', context)


def campaign_details(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)

    if campaign.state == Campaign.STATE_DRAFT:
        raise Http404()  # Prevent requesting unpublished campaigns

    backers_count = Transaction.objects.filter(campaign=campaign, confirmed=True).count()
    context = {'campaign': campaign, 'backers_count': backers_count}
    return render(request, 'crowdfunding/campaign_details.html', context)


def campaign_donate(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)

    if campaign.is_finished():
        raise Http404()  # Prevent donate request for finished campaign

    if not request.user.is_authenticated():
        # Collect unregistered user personal data for the history of donations
        new_user_form = DonateNewUserForm(request.POST or None)

        if new_user_form.is_valid():
            payer_user = new_user_form.save(commit=False)
            payer_user.set_unusable_password()
        else:
            payer_user = None
    else:
        payer_user = request.user
        new_user_form = None

    donate_form = FormDonate(request.POST or None)
    if payer_user and donate_form.is_valid():
        transaction = donate_form.save(commit=False)
        payer_user.save()
        transaction.payer = payer_user
        transaction.campaign = campaign
        transaction.is_public = donate_form.cleaned_data['is_public']

        # For testing purposes, currently, all transactions are confirmed instantly
        transaction.confirm()
        transaction.save()

        # Create Ginger's transaction right here
        description = "Payment for {}".format(campaign.desc_headline)
        order_url = create_ginger_transaction(transaction.amount*100, description, pk)

        # Redirect to the PSP payment page

        return redirect(order_url)

    context = {'campaign': campaign, 'donate_form': donate_form, 'new_user_form': new_user_form}
    return render(request, 'crowdfunding/campaign_donate.html', context)


def donate_instruction(request, transaction_pk, campaign_pk):
    transaction = get_object_or_404(Transaction, pk=transaction_pk)
    # Here transaction initialization should take place
    # For testing purposes, currently, all transactions are confirmed instantly
    transaction.confirm()
    messages.success(request, _('Thanks for your donation!'))

    return render(request, 'crowdfunding/donate_instruction.html',
                  {'pk': transaction_pk, 'campaign_pk': campaign_pk})


def ginger_return_redirect(request):

    # Happy flow: every transaction is successful! :)

    # Redirect user back to the campaign details page

    # Message for the next view
    messages.success(request, _('Thanks for your donation!'))
    campaign_pk = request.GET.get('campaign_pk')

    return redirect('crowdfunding:campaign_details', pk=campaign_pk)


# UTILS

def create_ginger_transaction(amount, description, campaign_pk):
    """
    :return: Order URL - leading to the payment page with PM selection
    """

    order_creation_endpoint = settings.GINGER_API_ENDPOINT + 'v1/orders/'

    auth_token = 'Basic ' + (base64.b64encode((settings.MARKETPLACE_MERCHANT_API_KEY + ':').encode())).decode()
    headers = {
        'Authorization': auth_token,
        'Content-Type': 'application/json'
    }

    body = {
        'currency': 'EUR',
        'amount': amount,
        # campaign_pk used to redirect to the page of the campaign for which transaction was processed
        'return_url': settings.COMEO_ORDER_RETURN_URL.format(campaign_pk),
        'description': description
    }

    r = requests.post(order_creation_endpoint, json=body, headers=headers)
    order_payload = r.json()

    log.info('Creating Ginger transaction')
    log.debug(order_payload)

    return order_payload['order_url']
