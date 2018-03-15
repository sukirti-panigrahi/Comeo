from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from apps.profiles.models import ComeoUser


class Tag(models.Model):
    name = models.CharField(max_length=100)


class Campaign(models.Model):

    STATE_DRAFT = 'draft'
    STATE_PUBLIC = 'public'
    STATE_FINISHED_SUCCESSFULLY = 'STATE_FINISHED_SUCCESSFULLY'
    STATE_FINISHED_NON_SUCCESSFULLY = 'STATE_FINISHED_NON_SUCCESSFULLY'

    # funding choices
    FUND_CONDITIONAL = 'conditional'
    FUND_UNCONDITIONAL = 'unconditional'

    FUND_TYPES = (
        (FUND_CONDITIONAL, 'Conditional funding'),
        (FUND_UNCONDITIONAL, 'Unconditional funding'),
    )

    # Duration range for choices
    DURATION_CHOICES = zip(range(1, 31), range(1, 31))

    desc_headline = models.CharField(_('Campaign headline'), max_length=300)
    desc_preview = models.TextField(_('Short description'), max_length=400)
    sum_goal = models.PositiveIntegerField()
    duration = models.PositiveSmallIntegerField(choices=DURATION_CHOICES)
    image_main = models.ImageField(verbose_name=_('Campaign image'), blank=True,
                                   upload_to='campaigns_images')
    desc_main = models.TextField(_('Description'))
    collected_sum = models.PositiveIntegerField(blank=True, default=0)
    editors = models.ManyToManyField(ComeoUser, related_name='campaign_editors',
                                     verbose_name=_('campaign editors'))
    owner = models.ForeignKey(ComeoUser, verbose_name=_('campaign owner'), null=True)
    state = models.CharField(_('State'), max_length=50, default=STATE_DRAFT)
    tags = models.ManyToManyField(Tag, verbose_name=_('Tags'), blank=True)
    funding_type = models.CharField(verbose_name=_('Funding type'), max_length=50,
                                    choices=FUND_TYPES, default=FUND_UNCONDITIONAL)
    date_start = models.DateField(_('start date'), null=True)
    date_finish = models.DateField(_('finish date'), null=True)
    date_created = models.DateTimeField(_('creation date'), default=timezone.now)
    views_count = models.PositiveIntegerField(_('view count'), default=0)

    def income_transaction(self, transaction):
        self.collected_sum += transaction.amount
        self.save()

    def days_to_finish(self):
        now = timezone.now().date()
        if self.date_finish:
            days_left = self.date_finish - now
            return days_left.days + 1

    def is_finished(self):
        return self.state in [self.STATE_FINISHED_SUCCESSFULLY, self.STATE_FINISHED_NON_SUCCESSFULLY]

    def check_finalization_goal(self):

        if self.collected_sum >= self.sum_goal:
            self.state = Campaign.STATE_FINISHED_SUCCESSFULLY
            self.finish_side_effects()
            self.save()

    def finish_side_effects(self):
        pass


class Transaction(models.Model):

    METHOD_CARD = 'METHOD_CARD'
    METHOD_TERMINAL = 'METHOD_TERMINAL'

    PAYMENT_METHODS = (
        (METHOD_CARD, 'Bank card'),
        (METHOD_TERMINAL, 'Terminal'),
    )

    amount = models.PositiveSmallIntegerField()
    method = models.CharField(choices=PAYMENT_METHODS, default=METHOD_CARD, max_length=40)
    campaign = models.ForeignKey(Campaign)
    payer = models.ForeignKey(ComeoUser)
    external_id = models.CharField(max_length=150, null=True)
    date_created = models.DateTimeField(default=timezone.now)
    confirmed = models.BooleanField(default=False)  # updated when transaction is captured by PSP
    date_confirmed = models.DateTimeField(null=True)
    is_public = models.BooleanField(default=True)

    def confirm(self):
        """
        This method should be called when transaction confirmation is received from the PSP
        """
        self.campaign.income_transaction(self)
        # try to finilize campaign on every new confirmed transaction
        self.campaign.check_finalization_goal()
        self.date_confirmed = timezone.now()
        self.confirmed = True
        self.save()
