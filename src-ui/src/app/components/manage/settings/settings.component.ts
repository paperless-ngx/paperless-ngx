import {
  Component,
  Inject,
  LOCALE_ID,
  OnInit,
  OnDestroy,
  AfterViewInit,
} from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import {
  LanguageOption,
  SettingsService,
} from 'src/app/services/settings.service'
import { Toast, ToastService } from 'src/app/services/toast.service'
import { dirtyCheck, DirtyComponent } from '@ngneat/dirty-check-forms'
import {
  Observable,
  Subscription,
  BehaviorSubject,
  first,
  tap,
  takeUntil,
  Subject,
} from 'rxjs'
import { SETTINGS_KEYS } from 'src/app/data/paperless-uisettings'
import { ActivatedRoute } from '@angular/router'
import { ViewportScroller } from '@angular/common'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'
import { PaperlessMailAccount } from 'src/app/data/paperless-mail-account'
import { PaperlessMailRule } from 'src/app/data/paperless-mail-rule'
import { MailAccountService as MailAccountService } from 'src/app/services/rest/mail-account.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss'],
})
export class SettingsComponent
  implements OnInit, AfterViewInit, OnDestroy, DirtyComponent
{
  savedViewGroup = new FormGroup({})

  mailAccountGroup = new FormGroup({})
  mailRuleGroup = new FormGroup({})

  settingsForm = new FormGroup({
    bulkEditConfirmationDialogs: new FormControl(null),
    bulkEditApplyOnClose: new FormControl(null),
    documentListItemPerPage: new FormControl(null),
    slimSidebarEnabled: new FormControl(null),
    darkModeUseSystem: new FormControl(null),
    darkModeEnabled: new FormControl(null),
    darkModeInvertThumbs: new FormControl(null),
    themeColor: new FormControl(null),
    useNativePdfViewer: new FormControl(null),
    displayLanguage: new FormControl(null),
    dateLocale: new FormControl(null),
    dateFormat: new FormControl(null),
    commentsEnabled: new FormControl(null),
    updateCheckingEnabled: new FormControl(null),

    notificationsConsumerNewDocument: new FormControl(null),
    notificationsConsumerSuccess: new FormControl(null),
    notificationsConsumerFailed: new FormControl(null),
    notificationsConsumerSuppressOnDashboard: new FormControl(null),

    savedViews: this.savedViewGroup,

    mailAccounts: this.mailAccountGroup,
    mailRules: this.mailRuleGroup,
  })

  savedViews: PaperlessSavedView[]

  mailAccounts: PaperlessMailAccount[]
  mailRules: PaperlessMailRule[]

  store: BehaviorSubject<any>
  storeSub: Subscription
  isDirty$: Observable<boolean>
  isDirty: boolean = false
  unsubscribeNotifier: Subject<any> = new Subject()
  savePending: boolean = false

  get computedDateLocale(): string {
    return (
      this.settingsForm.value.dateLocale ||
      this.settingsForm.value.displayLanguage ||
      this.currentLocale
    )
  }

  constructor(
    public savedViewService: SavedViewService,
    public mailAccountService: MailAccountService,
    public mailRuleService: MailRuleService,
    private documentListViewService: DocumentListViewService,
    private toastService: ToastService,
    private settings: SettingsService,
    @Inject(LOCALE_ID) public currentLocale: string,
    private viewportScroller: ViewportScroller,
    private activatedRoute: ActivatedRoute,
    public readonly tourService: TourService
  ) {
    this.settings.settingsSaved.subscribe(() => {
      if (!this.savePending) this.initialize()
    })
  }

  ngAfterViewInit(): void {
    if (this.activatedRoute.snapshot.fragment) {
      this.viewportScroller.scrollToAnchor(
        this.activatedRoute.snapshot.fragment
      )
    }
  }

  private getCurrentSettings() {
    return {
      bulkEditConfirmationDialogs: this.settings.get(
        SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS
      ),
      bulkEditApplyOnClose: this.settings.get(
        SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE
      ),
      documentListItemPerPage: this.settings.get(
        SETTINGS_KEYS.DOCUMENT_LIST_SIZE
      ),
      slimSidebarEnabled: this.settings.get(SETTINGS_KEYS.SLIM_SIDEBAR),
      darkModeUseSystem: this.settings.get(SETTINGS_KEYS.DARK_MODE_USE_SYSTEM),
      darkModeEnabled: this.settings.get(SETTINGS_KEYS.DARK_MODE_ENABLED),
      darkModeInvertThumbs: this.settings.get(
        SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED
      ),
      themeColor: this.settings.get(SETTINGS_KEYS.THEME_COLOR),
      useNativePdfViewer: this.settings.get(
        SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER
      ),
      displayLanguage: this.settings.getLanguage(),
      dateLocale: this.settings.get(SETTINGS_KEYS.DATE_LOCALE),
      dateFormat: this.settings.get(SETTINGS_KEYS.DATE_FORMAT),
      commentsEnabled: this.settings.get(SETTINGS_KEYS.COMMENTS_ENABLED),
      updateCheckingEnabled: this.settings.get(
        SETTINGS_KEYS.UPDATE_CHECKING_ENABLED
      ),
      notificationsConsumerNewDocument: this.settings.get(
        SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT
      ),
      notificationsConsumerSuccess: this.settings.get(
        SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUCCESS
      ),
      notificationsConsumerFailed: this.settings.get(
        SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_FAILED
      ),
      notificationsConsumerSuppressOnDashboard: this.settings.get(
        SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD
      ),
      savedViews: {},
      mailAccounts: {},
      mailRules: {},
    }
  }

  ngOnInit() {
    this.savedViewService.listAll().subscribe((r) => {
      this.savedViews = r.results

      this.mailAccountService.listAll().subscribe((r) => {
        this.mailAccounts = r.results

        this.mailRuleService.listAll().subscribe((r) => {
          this.mailRules = r.results

          this.initialize()
        })
      })
    })
  }

  initialize() {
    this.unsubscribeNotifier.next(true)

    let storeData = this.getCurrentSettings()

    for (let view of this.savedViews) {
      storeData.savedViews[view.id.toString()] = {
        id: view.id,
        name: view.name,
        show_on_dashboard: view.show_on_dashboard,
        show_in_sidebar: view.show_in_sidebar,
      }
      this.savedViewGroup.addControl(
        view.id.toString(),
        new FormGroup({
          id: new FormControl(null),
          name: new FormControl(null),
          show_on_dashboard: new FormControl(null),
          show_in_sidebar: new FormControl(null),
        })
      )
    }

    for (let account of this.mailAccounts) {
      storeData.mailAccounts[account.id.toString()] = {
        id: account.id,
        name: account.name,
        imap_server: account.imap_server,
        imap_port: account.imap_port,
        imap_security: account.imap_security,
        username: account.username,
        password: account.password,
        character_set: account.character_set,
      }
      this.mailAccountGroup.addControl(
        account.id.toString(),
        new FormGroup({
          id: new FormControl(null),
          name: new FormControl(null),
          imap_server: new FormControl(null),
          imap_port: new FormControl(null),
          imap_security: new FormControl(null),
          username: new FormControl(null),
          password: new FormControl(null),
          character_set: new FormControl(null),
        })
      )
    }

    for (let rule of this.mailRules) {
      storeData.mailRules[rule.id.toString()] = {
        name: rule.name,
        order: rule.order,
        account: rule.account,
        folder: rule.folder,
        filter_from: rule.filter_from,
        filter_subject: rule.filter_subject,
        filter_body: rule.filter_body,
        filter_attachment_filename: rule.filter_attachment_filename,
        maximum_age: rule.maximum_age,
        attachment_type: rule.attachment_type,
        action: rule.action,
        action_parameter: rule.action_parameter,
        assign_title_from: rule.assign_title_from,
        assign_tags: rule.assign_tags,
        assign_document_type: rule.assign_document_type,
        assign_correspondent_from: rule.assign_correspondent_from,
        assign_correspondent: rule.assign_correspondent,
      }
      this.mailRuleGroup.addControl(
        rule.id.toString(),
        new FormGroup({
          name: new FormControl(null),
          order: new FormControl(null),
          account: new FormControl(null),
          folder: new FormControl(null),
          filter_from: new FormControl(null),
          filter_subject: new FormControl(null),
          filter_body: new FormControl(null),
          filter_attachment_filename: new FormControl(null),
          maximum_age: new FormControl(null),
          attachment_type: new FormControl(null),
          action: new FormControl(null),
          action_parameter: new FormControl(null),
          assign_title_from: new FormControl(null),
          assign_tags: new FormControl(null),
          assign_document_type: new FormControl(null),
          assign_correspondent_from: new FormControl(null),
          assign_correspondent: new FormControl(null),
        })
      )
    }

    this.store = new BehaviorSubject(storeData)

    this.storeSub = this.store.asObservable().subscribe((state) => {
      this.settingsForm.patchValue(state, { emitEvent: false })
    })

    // Initialize dirtyCheck
    this.isDirty$ = dirtyCheck(this.settingsForm, this.store.asObservable())

    // Record dirty in case we need to 'undo' appearance settings if not saved on close
    this.isDirty$
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((dirty) => {
        this.isDirty = dirty
      })

    // "Live" visual changes prior to save
    this.settingsForm.valueChanges
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.settings.updateAppearanceSettings(
          this.settingsForm.get('darkModeUseSystem').value,
          this.settingsForm.get('darkModeEnabled').value,
          this.settingsForm.get('themeColor').value
        )
      })
  }

  ngOnDestroy() {
    if (this.isDirty) this.settings.updateAppearanceSettings() // in case user changed appearance but didnt save
    this.storeSub && this.storeSub.unsubscribe()
  }

  deleteSavedView(savedView: PaperlessSavedView) {
    this.savedViewService.delete(savedView).subscribe(() => {
      this.savedViewGroup.removeControl(savedView.id.toString())
      this.savedViews.splice(this.savedViews.indexOf(savedView), 1)
      this.toastService.showInfo(
        $localize`Saved view "${savedView.name}" deleted.`
      )
    })
  }

  private saveLocalSettings() {
    this.savePending = true
    const reloadRequired =
      this.settingsForm.value.displayLanguage !=
        this.store?.getValue()['displayLanguage'] || // displayLanguage is dirty
      (this.settingsForm.value.updateCheckingEnabled !=
        this.store?.getValue()['updateCheckingEnabled'] &&
        this.settingsForm.value.updateCheckingEnabled) // update checking was turned on

    this.settings.set(
      SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE,
      this.settingsForm.value.bulkEditApplyOnClose
    )
    this.settings.set(
      SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS,
      this.settingsForm.value.bulkEditConfirmationDialogs
    )
    this.settings.set(
      SETTINGS_KEYS.DOCUMENT_LIST_SIZE,
      this.settingsForm.value.documentListItemPerPage
    )
    this.settings.set(
      SETTINGS_KEYS.SLIM_SIDEBAR,
      this.settingsForm.value.slimSidebarEnabled
    )
    this.settings.set(
      SETTINGS_KEYS.DARK_MODE_USE_SYSTEM,
      this.settingsForm.value.darkModeUseSystem
    )
    this.settings.set(
      SETTINGS_KEYS.DARK_MODE_ENABLED,
      (this.settingsForm.value.darkModeEnabled == true).toString()
    )
    this.settings.set(
      SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED,
      (this.settingsForm.value.darkModeInvertThumbs == true).toString()
    )
    this.settings.set(
      SETTINGS_KEYS.THEME_COLOR,
      this.settingsForm.value.themeColor.toString()
    )
    this.settings.set(
      SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER,
      this.settingsForm.value.useNativePdfViewer
    )
    this.settings.set(
      SETTINGS_KEYS.DATE_LOCALE,
      this.settingsForm.value.dateLocale
    )
    this.settings.set(
      SETTINGS_KEYS.DATE_FORMAT,
      this.settingsForm.value.dateFormat
    )
    this.settings.set(
      SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT,
      this.settingsForm.value.notificationsConsumerNewDocument
    )
    this.settings.set(
      SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUCCESS,
      this.settingsForm.value.notificationsConsumerSuccess
    )
    this.settings.set(
      SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_FAILED,
      this.settingsForm.value.notificationsConsumerFailed
    )
    this.settings.set(
      SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD,
      this.settingsForm.value.notificationsConsumerSuppressOnDashboard
    )
    this.settings.set(
      SETTINGS_KEYS.COMMENTS_ENABLED,
      this.settingsForm.value.commentsEnabled
    )
    this.settings.set(
      SETTINGS_KEYS.UPDATE_CHECKING_ENABLED,
      this.settingsForm.value.updateCheckingEnabled
    )
    this.settings.setLanguage(this.settingsForm.value.displayLanguage)
    this.settings
      .storeSettings()
      .pipe(first())
      .pipe(tap(() => (this.savePending = false)))
      .subscribe({
        next: () => {
          this.store.next(this.settingsForm.value)
          this.documentListViewService.updatePageSize()
          this.settings.updateAppearanceSettings()
          let savedToast: Toast = {
            title: $localize`Settings saved`,
            content: $localize`Settings were saved successfully.`,
            delay: 500000,
          }
          if (reloadRequired) {
            ;(savedToast.content = $localize`Settings were saved successfully. Reload is required to apply some changes.`),
              (savedToast.actionName = $localize`Reload now`)
            savedToast.action = () => {
              location.reload()
            }
          }

          this.toastService.show(savedToast)
        },
        error: (error) => {
          this.toastService.showError(
            $localize`An error occurred while saving settings.`
          )
          console.log(error)
        },
      })
  }

  get displayLanguageOptions(): LanguageOption[] {
    return [{ code: '', name: $localize`Use system language` }].concat(
      this.settings.getLanguageOptions()
    )
  }

  get dateLocaleOptions(): LanguageOption[] {
    return [
      { code: '', name: $localize`Use date format of display language` },
    ].concat(this.settings.getDateLocaleOptions())
  }

  get today() {
    return new Date()
  }

  saveSettings() {
    let x = []
    for (let id in this.savedViewGroup.value) {
      x.push(this.savedViewGroup.value[id])
    }
    if (x.length > 0) {
      this.savedViewService.patchMany(x).subscribe(
        (s) => {
          this.saveLocalSettings()
        },
        (error) => {
          this.toastService.showError(
            $localize`Error while storing settings on server: ${JSON.stringify(
              error.error
            )}`
          )
        }
      )
    } else {
      this.saveLocalSettings()
    }
  }

  clearThemeColor() {
    this.settingsForm.get('themeColor').patchValue('')
  }
}
