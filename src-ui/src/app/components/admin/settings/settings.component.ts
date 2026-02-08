import { AsyncPipe, ViewportScroller } from '@angular/common'
import {
  AfterViewInit,
  Component,
  LOCALE_ID,
  OnDestroy,
  OnInit,
  inject,
} from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { ActivatedRoute, Router } from '@angular/router'
import {
  NgbModal,
  NgbModalRef,
  NgbNavChangeEvent,
  NgbNavModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { DirtyComponent, dirtyCheck } from '@ngneat/dirty-check-forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
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
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { GroupService } from 'src/app/services/rest/group.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { UserService } from 'src/app/services/rest/user.service'
import {
  LanguageOption,
  SettingsService,
} from 'src/app/services/settings.service'
import { SystemStatusService } from 'src/app/services/system-status.service'
import { Toast, ToastService } from 'src/app/services/toast.service'
import { locationReload } from 'src/app/utils/navigation'
import { CheckComponent } from '../../common/input/check/check.component'
import { ColorComponent } from '../../common/input/color/color.component'
import { PermissionsGroupComponent } from '../../common/input/permissions/permissions-group/permissions-group.component'
import { PermissionsUserComponent } from '../../common/input/permissions/permissions-user/permissions-user.component'
import { SelectComponent } from '../../common/input/select/select.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { PdfEditorEditMode } from '../../common/pdf-editor/pdf-editor-edit-mode'
import { PdfZoomScale } from '../../common/pdf-viewer/pdf-viewer.types'
import { SystemStatusDialogComponent } from '../../common/system-status-dialog/system-status-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

enum SettingsNavIDs {
  General = 1,
  Documents = 2,
  Permissions = 3,
  Notifications = 4,
}

const systemLanguage = { code: '', name: $localize`Use system language` }
const systemDateFormat = {
  code: '',
  name: $localize`Use date format of display language`,
}

export enum DocumentDetailFieldID {
  ArchiveSerialNumber = 'archive_serial_number',
  Correspondent = 'correspondent',
  DocumentType = 'document_type',
  StoragePath = 'storage_path',
  Tags = 'tags',
}

const documentDetailFieldOptions = [
  {
    id: DocumentDetailFieldID.ArchiveSerialNumber,
    label: $localize`Archive serial number`,
  },
  { id: DocumentDetailFieldID.Correspondent, label: $localize`Correspondent` },
  { id: DocumentDetailFieldID.DocumentType, label: $localize`Document type` },
  { id: DocumentDetailFieldID.StoragePath, label: $localize`Storage path` },
  { id: DocumentDetailFieldID.Tags, label: $localize`Tags` },
]

@Component({
  selector: 'pngx-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss'],
  imports: [
    PageHeaderComponent,
    CheckComponent,
    ColorComponent,
    SelectComponent,
    PermissionsGroupComponent,
    PermissionsUserComponent,
    CustomDatePipe,
    IfPermissionsDirective,
    AsyncPipe,
    FormsModule,
    ReactiveFormsModule,
    NgbNavModule,
    NgbPopoverModule,
    NgxBootstrapIconsModule,
  ],
})
export class SettingsComponent
  extends ComponentWithPermissions
  implements OnInit, AfterViewInit, OnDestroy, DirtyComponent
{
  private documentListViewService = inject(DocumentListViewService)
  private toastService = inject(ToastService)
  private settings = inject(SettingsService)
  currentLocale = inject(LOCALE_ID)
  private viewportScroller = inject(ViewportScroller)
  private activatedRoute = inject(ActivatedRoute)
  readonly tourService = inject(TourService)
  private usersService = inject(UserService)
  private groupsService = inject(GroupService)
  private router = inject(Router)
  permissionsService = inject(PermissionsService)
  private modalService = inject(NgbModal)
  private systemStatusService = inject(SystemStatusService)
  private savedViewsService = inject(SavedViewService)

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
    pdfViewerDefaultZoom: new FormControl(null),
    pdfEditorDefaultEditMode: new FormControl(null),
    documentEditingRemoveInboxTags: new FormControl(null),
    documentEditingOverlayThumbnail: new FormControl(null),
    documentDetailsHiddenFields: new FormControl([]),
    searchDbOnly: new FormControl(null),
    searchLink: new FormControl(null),

    notificationsConsumerNewDocument: new FormControl(null),
    notificationsConsumerSuccess: new FormControl(null),
    notificationsConsumerFailed: new FormControl(null),
    notificationsConsumerSuppressOnDashboard: new FormControl(null),

    savedViewsWarnOnUnsavedChange: new FormControl(null),
    sidebarViewsShowCount: new FormControl(null),
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

  public readonly PdfZoomScale = PdfZoomScale

  public readonly PdfEditorEditMode = PdfEditorEditMode

  public readonly documentDetailFieldOptions = documentDetailFieldOptions

  get systemStatusHasErrors(): boolean {
    return (
      this.systemStatus.database.status === SystemStatusItemStatus.ERROR ||
      this.systemStatus.tasks.redis_status === SystemStatusItemStatus.ERROR ||
      this.systemStatus.tasks.celery_status === SystemStatusItemStatus.ERROR ||
      this.systemStatus.tasks.index_status === SystemStatusItemStatus.ERROR ||
      this.systemStatus.tasks.classifier_status ===
        SystemStatusItemStatus.ERROR ||
      this.systemStatus.tasks.sanity_check_status ===
        SystemStatusItemStatus.ERROR ||
      this.systemStatus.websocket_connected === SystemStatusItemStatus.ERROR
    )
  }

  get computedDateLocale(): string {
    return (
      this.settingsForm.value.dateLocale ||
      this.settingsForm.value.displayLanguage ||
      this.currentLocale
    )
  }

  constructor() {
    super()
    this.settings.settingsSaved.subscribe(() => {
      if (!this.savePending) this.initialize()
      this.savedViewsService.maybeRefreshDocumentCounts()
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
      pdfViewerDefaultZoom: this.settings.get(
        SETTINGS_KEYS.PDF_VIEWER_ZOOM_SETTING
      ),
      pdfEditorDefaultEditMode: this.settings.get(
        SETTINGS_KEYS.PDF_EDITOR_DEFAULT_EDIT_MODE
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
      sidebarViewsShowCount: this.settings.get(
        SETTINGS_KEYS.SIDEBAR_VIEWS_SHOW_COUNT
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
      documentDetailsHiddenFields: this.settings.get(
        SETTINGS_KEYS.DOCUMENT_DETAILS_HIDDEN_FIELDS
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
      SETTINGS_KEYS.PDF_VIEWER_ZOOM_SETTING,
      this.settingsForm.value.pdfViewerDefaultZoom
    )
    this.settings.set(
      SETTINGS_KEYS.PDF_EDITOR_DEFAULT_EDIT_MODE,
      this.settingsForm.value.pdfEditorDefaultEditMode
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
      SETTINGS_KEYS.SIDEBAR_VIEWS_SHOW_COUNT,
      this.settingsForm.value.sidebarViewsShowCount
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
      SETTINGS_KEYS.DOCUMENT_DETAILS_HIDDEN_FIELDS,
      this.settingsForm.value.documentDetailsHiddenFields
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
              locationReload()
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

  isDocumentDetailFieldShown(fieldId: string): boolean {
    const hiddenFields =
      this.settingsForm.value.documentDetailsHiddenFields || []
    return !hiddenFields.includes(fieldId)
  }

  toggleDocumentDetailField(fieldId: string, checked: boolean) {
    const hiddenFields = new Set(
      this.settingsForm.value.documentDetailsHiddenFields || []
    )
    if (checked) {
      hiddenFields.delete(fieldId)
    } else {
      hiddenFields.add(fieldId)
    }
    this.settingsForm
      .get('documentDetailsHiddenFields')
      .setValue(Array.from(hiddenFields))
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
