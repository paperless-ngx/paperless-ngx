import { ViewportScroller } from '@angular/common'
import {
  AfterViewInit,
  Component,
  Inject,
  LOCALE_ID,
  OnDestroy,
  OnInit,
} from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { ActivatedRoute, Router } from '@angular/router'
import {
  NgbModal,
  NgbModalRef,
  NgbNavChangeEvent,
} from '@ng-bootstrap/ng-bootstrap'
import { DirtyComponent, dirtyCheck } from '@ngneat/dirty-check-forms'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'
import {
  BehaviorSubject,
  Observable,
  Subject,
  Subscription,
  first,
  takeUntil,
  tap,
} from 'rxjs'
import { Group } from 'src/app/data/group'
import {
  SystemStatus,
  SystemStatusItemStatus,
} from 'src/app/data/system-status'
import { GlobalSearchType, SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { User } from 'src/app/data/user'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { GroupService } from 'src/app/services/rest/group.service'
import { UserService } from 'src/app/services/rest/user.service'
import {
  LanguageOption,
  SettingsService,
} from 'src/app/services/settings.service'
import { SystemStatusService } from 'src/app/services/system-status.service'
import { Toast, ToastService } from 'src/app/services/toast.service'
import { SystemStatusDialogComponent } from '../../common/system-status-dialog/system-status-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

enum SettingsNavIDs {
  General = 1,
  Permissions = 2,
  Notifications = 3,
  SavedViews = 4,
}

const systemLanguage = { code: '', name: $localize`Use system language` }
const systemDateFormat = {
  code: '',
  name: $localize`Use date format of display language`,
}

@Component({
  selector: 'pngx-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss'],
})
export class SettingsComponent
  extends ComponentWithPermissions
  implements OnInit, AfterViewInit, OnDestroy, DirtyComponent
{
  activeNavID: number

  settingsForm = new FormGroup({
    bulkEditConfirmationDialogs: new FormControl(null),
    bulkEditApplyOnClose: new FormControl(null),
    documentListItemPerPage: new FormControl(null),
    slimSidebarEnabled: new FormControl(null),
    darkModeUseSystem: new FormControl(null),
    darkModeEnabled: new FormControl(null),
    darkModeInvertThumbs: new FormControl(null),
    themeColor: new FormControl(null),
    displayLanguage: new FormControl(null),
    dateLocale: new FormControl(null),
    dateFormat: new FormControl(null),
    notesEnabled: new FormControl(null),
    updateCheckingEnabled: new FormControl(null),
    defaultPermsOwner: new FormControl(null),
    defaultPermsViewUsers: new FormControl(null),
    defaultPermsViewGroups: new FormControl(null),
    defaultPermsEditUsers: new FormControl(null),
    defaultPermsEditGroups: new FormControl(null),
    useNativePdfViewer: new FormControl(null),
    documentEditingRemoveInboxTags: new FormControl(null),
    documentEditingOverlayThumbnail: new FormControl(null),
    searchDbOnly: new FormControl(null),
    searchLink: new FormControl(null),

    notificationsConsumerNewDocument: new FormControl(null),
    notificationsConsumerSuccess: new FormControl(null),
    notificationsConsumerFailed: new FormControl(null),
    notificationsConsumerSuppressOnDashboard: new FormControl(null),

    savedViewsWarnOnUnsavedChange: new FormControl(null),
  })

  SettingsNavIDs = SettingsNavIDs

  store: BehaviorSubject<any>
  storeSub: Subscription
  isDirty$: Observable<boolean>
  isDirty: boolean = false
  unsubscribeNotifier: Subject<any> = new Subject()
  savePending: boolean = false

  users: User[]
  groups: Group[]

  public systemStatus: SystemStatus

  public readonly GlobalSearchType = GlobalSearchType

  get systemStatusHasErrors(): boolean {
    return (
      this.systemStatus.database.status === SystemStatusItemStatus.ERROR ||
      this.systemStatus.tasks.redis_status === SystemStatusItemStatus.ERROR ||
      this.systemStatus.tasks.celery_status === SystemStatusItemStatus.ERROR ||
      this.systemStatus.tasks.index_status === SystemStatusItemStatus.ERROR ||
      this.systemStatus.tasks.classifier_status === SystemStatusItemStatus.ERROR
    )
  }

  get computedDateLocale(): string {
    return (
      this.settingsForm.value.dateLocale ||
      this.settingsForm.value.displayLanguage ||
      this.currentLocale
    )
  }

  constructor(
    private documentListViewService: DocumentListViewService,
    private toastService: ToastService,
    private settings: SettingsService,
    @Inject(LOCALE_ID) public currentLocale: string,
    private viewportScroller: ViewportScroller,
    private activatedRoute: ActivatedRoute,
    public readonly tourService: TourService,
    private usersService: UserService,
    private groupsService: GroupService,
    private router: Router,
    public permissionsService: PermissionsService,
    private modalService: NgbModal,
    private systemStatusService: SystemStatusService
  ) {
    super()
    this.settings.settingsSaved.subscribe(() => {
      if (!this.savePending) this.initialize()
    })
  }

  ngOnInit() {
    this.initialize()

    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.User
      )
    ) {
      this.usersService
        .listAll()
        .pipe(first())
        .subscribe({
          next: (r) => {
            this.users = r.results
          },
          error: (e) => {
            this.toastService.showError($localize`Error retrieving users`, e)
          },
        })
    }

    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Group
      )
    ) {
      this.groupsService
        .listAll()
        .pipe(first())
        .subscribe({
          next: (r) => {
            this.groups = r.results
          },
          error: (e) => {
            this.toastService.showError($localize`Error retrieving groups`, e)
          },
        })
    }

    this.activatedRoute.paramMap.subscribe((paramMap) => {
      const section = paramMap.get('section')
      if (section) {
        const navIDKey: string = Object.keys(SettingsNavIDs).find(
          (navID) => navID.toLowerCase() == section
        )
        if (navIDKey) {
          this.activeNavID = SettingsNavIDs[navIDKey]
        }
      }
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
      notesEnabled: this.settings.get(SETTINGS_KEYS.NOTES_ENABLED),
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
      savedViewsWarnOnUnsavedChange: this.settings.get(
        SETTINGS_KEYS.SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE
      ),
      defaultPermsOwner: this.settings.get(SETTINGS_KEYS.DEFAULT_PERMS_OWNER),
      defaultPermsViewUsers: this.settings.get(
        SETTINGS_KEYS.DEFAULT_PERMS_VIEW_USERS
      ),
      defaultPermsViewGroups: this.settings.get(
        SETTINGS_KEYS.DEFAULT_PERMS_VIEW_GROUPS
      ),
      defaultPermsEditUsers: this.settings.get(
        SETTINGS_KEYS.DEFAULT_PERMS_EDIT_USERS
      ),
      defaultPermsEditGroups: this.settings.get(
        SETTINGS_KEYS.DEFAULT_PERMS_EDIT_GROUPS
      ),
      documentEditingRemoveInboxTags: this.settings.get(
        SETTINGS_KEYS.DOCUMENT_EDITING_REMOVE_INBOX_TAGS
      ),
      documentEditingOverlayThumbnail: this.settings.get(
        SETTINGS_KEYS.DOCUMENT_EDITING_OVERLAY_THUMBNAIL
      ),
      searchDbOnly: this.settings.get(SETTINGS_KEYS.SEARCH_DB_ONLY),
      searchLink: this.settings.get(SETTINGS_KEYS.SEARCH_FULL_TYPE),
    }
  }

  onNavChange(navChangeEvent: NgbNavChangeEvent) {
    const [foundNavIDkey] = Object.entries(SettingsNavIDs).find(
      ([, navIDValue]) => navIDValue == navChangeEvent.nextId
    )
    if (foundNavIDkey)
      // if its dirty we need to wait for confirmation
      this.router
        .navigate(['settings', foundNavIDkey.toLowerCase()])
        .then((navigated) => {
          if (!navigated && this.isDirty) {
            this.activeNavID = navChangeEvent.activeId
          } else if (navigated && this.isDirty) {
            this.initialize()
          }
        })
  }

  initialize(resetSettings: boolean = true) {
    this.unsubscribeNotifier.next(true)

    const currentFormValue = this.settingsForm.value

    let storeData = this.getCurrentSettings()

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

    if (!resetSettings && currentFormValue) {
      // prevents loss of unsaved changes
      this.settingsForm.patchValue(currentFormValue)
    }

    if (this.permissionsService.isAdmin()) {
      this.systemStatusService.get().subscribe((status) => {
        this.systemStatus = status
      })
    }
  }

  ngOnDestroy() {
    if (this.isDirty) this.settings.updateAppearanceSettings() // in case user changed appearance but didn't save
    this.storeSub && this.storeSub.unsubscribe()
  }

  public saveSettings() {
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
      this.settingsForm.value.themeColor
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
      SETTINGS_KEYS.NOTES_ENABLED,
      this.settingsForm.value.notesEnabled
    )
    this.settings.set(
      SETTINGS_KEYS.UPDATE_CHECKING_ENABLED,
      this.settingsForm.value.updateCheckingEnabled
    )
    this.settings.set(
      SETTINGS_KEYS.SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE,
      this.settingsForm.value.savedViewsWarnOnUnsavedChange
    )
    this.settings.set(
      SETTINGS_KEYS.DEFAULT_PERMS_OWNER,
      this.settingsForm.value.defaultPermsOwner
    )
    this.settings.set(
      SETTINGS_KEYS.DEFAULT_PERMS_VIEW_USERS,
      this.settingsForm.value.defaultPermsViewUsers
    )
    this.settings.set(
      SETTINGS_KEYS.DEFAULT_PERMS_VIEW_GROUPS,
      this.settingsForm.value.defaultPermsViewGroups
    )
    this.settings.set(
      SETTINGS_KEYS.DEFAULT_PERMS_EDIT_USERS,
      this.settingsForm.value.defaultPermsEditUsers
    )
    this.settings.set(
      SETTINGS_KEYS.DEFAULT_PERMS_EDIT_GROUPS,
      this.settingsForm.value.defaultPermsEditGroups
    )
    this.settings.set(
      SETTINGS_KEYS.DOCUMENT_EDITING_REMOVE_INBOX_TAGS,
      this.settingsForm.value.documentEditingRemoveInboxTags
    )
    this.settings.set(
      SETTINGS_KEYS.DOCUMENT_EDITING_OVERLAY_THUMBNAIL,
      this.settingsForm.value.documentEditingOverlayThumbnail
    )
    this.settings.set(
      SETTINGS_KEYS.SEARCH_DB_ONLY,
      this.settingsForm.value.searchDbOnly
    )
    this.settings.set(
      SETTINGS_KEYS.SEARCH_FULL_TYPE,
      this.settingsForm.value.searchLink
    )
    this.settings.setLanguage(this.settingsForm.value.displayLanguage)
    this.settings
      .storeSettings()
      .pipe(first())
      .pipe(tap(() => (this.savePending = false)))
      .subscribe({
        next: () => {
          this.store.next(this.settingsForm.value)
          this.settings.updateAppearanceSettings()
          this.settings.initializeDisplayFields()
          let savedToast: Toast = {
            content: $localize`Settings were saved successfully.`,
            delay: 5000,
          }
          if (reloadRequired) {
            savedToast.content = $localize`Settings were saved successfully. Reload is required to apply some changes.`
            savedToast.actionName = $localize`Reload now`
            savedToast.action = () => {
              location.reload()
            }
          }

          this.toastService.show(savedToast)
        },
        error: (error) => {
          this.toastService.showError(
            $localize`An error occurred while saving settings.`,
            error
          )
        },
      })
  }

  get displayLanguageOptions(): LanguageOption[] {
    return [systemLanguage].concat(this.settings.getLanguageOptions())
  }

  get dateLocaleOptions(): LanguageOption[] {
    return [systemDateFormat].concat(this.settings.getDateLocaleOptions())
  }

  get today() {
    return new Date()
  }

  reset() {
    this.settingsForm.patchValue(this.store.getValue())
  }

  clearThemeColor() {
    this.settingsForm.get('themeColor').patchValue('')
  }

  showSystemStatus() {
    const modal: NgbModalRef = this.modalService.open(
      SystemStatusDialogComponent,
      {
        size: 'xl',
      }
    )
    modal.componentInstance.status = this.systemStatus
  }
}
