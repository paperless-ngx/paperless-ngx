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
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { NgbModal, NgbNavChangeEvent } from '@ng-bootstrap/ng-bootstrap'
import { Results } from 'src/app/data/results'
import { UserService } from 'src/app/services/rest/user.service'
import { GroupService } from 'src/app/services/rest/group.service'
import { PaperlessUser } from 'src/app/data/paperless-user'
import { PaperlessGroup } from 'src/app/data/paperless-group'
import { UserEditDialogComponent } from '../../common/edit-dialog/user-edit-dialog/user-edit-dialog.component'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { GroupEditDialogComponent } from '../../common/edit-dialog/group-edit-dialog/group-edit-dialog.component'

enum SettingsNavIDs {
  General = 1,
  Notifications = 2,
  SavedViews = 3,
  Mail = 4,
  UsersGroups = 5,
}

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss'],
})
export class SettingsComponent
  extends ComponentWithPermissions
  implements OnInit, AfterViewInit, OnDestroy, DirtyComponent
{
  SettingsNavIDs = SettingsNavIDs
  activeNavID: number

  savedViewGroup = new FormGroup({})
  usersGroup = new FormGroup({})
  groupsGroup = new FormGroup({})

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
    savedViews: this.savedViewGroup,
    displayLanguage: new FormControl(null),
    dateLocale: new FormControl(null),
    dateFormat: new FormControl(null),
    notificationsConsumerNewDocument: new FormControl(null),
    notificationsConsumerSuccess: new FormControl(null),
    notificationsConsumerFailed: new FormControl(null),
    notificationsConsumerSuppressOnDashboard: new FormControl(null),
    commentsEnabled: new FormControl(null),
    updateCheckingEnabled: new FormControl(null),
    usersGroup: this.usersGroup,
    groupsGroup: this.groupsGroup,
  })

  savedViews: PaperlessSavedView[]

  store: BehaviorSubject<any>
  storeSub: Subscription
  isDirty$: Observable<boolean>
  isDirty: boolean = false
  unsubscribeNotifier: Subject<any> = new Subject()
  savePending: boolean = false

  users: PaperlessUser[]
  groups: PaperlessGroup[]

  get computedDateLocale(): string {
    return (
      this.settingsForm.value.dateLocale ||
      this.settingsForm.value.displayLanguage ||
      this.currentLocale
    )
  }

  constructor(
    public savedViewService: SavedViewService,
    private documentListViewService: DocumentListViewService,
    private toastService: ToastService,
    private settings: SettingsService,
    @Inject(LOCALE_ID) public currentLocale: string,
    private viewportScroller: ViewportScroller,
    private activatedRoute: ActivatedRoute,
    public readonly tourService: TourService,
    private usersService: UserService,
    private groupsService: GroupService,
    private modalService: NgbModal
  ) {
    super()
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
      savedViews: {},
      displayLanguage: this.settings.getLanguage(),
      dateLocale: this.settings.get(SETTINGS_KEYS.DATE_LOCALE),
      dateFormat: this.settings.get(SETTINGS_KEYS.DATE_FORMAT),
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
      commentsEnabled: this.settings.get(SETTINGS_KEYS.COMMENTS_ENABLED),
      updateCheckingEnabled: this.settings.get(
        SETTINGS_KEYS.UPDATE_CHECKING_ENABLED
      ),
      usersGroup: {},
      groupsGroup: {},
    }
  }

  ngOnInit() {
    this.initialize()
  }

  // Load tab contents 'on demand', either on mouseover or focusin (i.e. before click) or on nav change event
  maybeInitializeTab(navIDorEvent: number | NgbNavChangeEvent): void {
    const navID =
      typeof navIDorEvent == 'number' ? navIDorEvent : navIDorEvent.nextId
    // initialize saved views
    if (navID == SettingsNavIDs.SavedViews && !this.savedViews) {
      this.savedViewService.listAll().subscribe((r) => {
        this.savedViews = r.results
        this.initialize()
      })
    } else if (
      (navID == SettingsNavIDs.UsersGroups && !this.users) ||
      !this.groups
    ) {
      this.usersService.listAll().subscribe((r) => {
        this.users = r.results

        this.groupsService.listAll().subscribe((r) => {
          this.groups = r.results
          this.initialize()
        })
      })
    }
  }

  initialize() {
    this.unsubscribeNotifier.next(true)

    let storeData = this.getCurrentSettings()

    if (this.savedViews) {
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
    }

    if (this.users && this.groups) {
      for (let user of this.users) {
        storeData.usersGroup[user.id.toString()] = {
          id: user.id,
          username: user.username,
          first_name: user.first_name,
          last_name: user.last_name,
          is_active: user.is_active,
          is_superuser: user.is_superuser,
          groups: user.groups,
          permissions: user.permissions,
        }
        this.usersGroup.addControl(
          user.id.toString(),
          new FormGroup({
            id: new FormControl(null),
            username: new FormControl(null),
            first_name: new FormControl(null),
            last_name: new FormControl(null),
            is_active: new FormControl(null),
            is_superuser: new FormControl(null),
            groups: new FormControl(null),
            permissions: new FormControl(null),
          })
        )
      }

      for (let group of this.groups) {
        storeData.groupsGroup[group.id.toString()] = {
          id: group.id,
          name: group.name,
          permissions: group.permissions,
        }
        this.groupsGroup.addControl(
          group.id.toString(),
          new FormGroup({
            id: new FormControl(null),
            name: new FormControl(null),
            permissions: new FormControl(null),
          })
        )
      }
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

  editUser(user: PaperlessUser) {
    var modal = this.modalService.open(UserEditDialogComponent, {
      backdrop: 'static',
      size: 'xl',
    })
    modal.componentInstance.dialogMode = user ? 'edit' : 'create'
    modal.componentInstance.object = user
    modal.componentInstance.success
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (newUser) => {
          this.toastService.showInfo(
            $localize`Saved user "${newUser.username}".`
          )
          this.usersService.listAll().subscribe((r) => {
            this.users = r.results
            this.initialize()
          })
        },
        error: (e) => {
          this.toastService.showError(
            $localize`Error saving user: ${e.toString()}.`
          )
        },
      })
  }

  deleteUser(user: PaperlessUser) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete user account`
    modal.componentInstance.messageBold = $localize`This operation will permanently this user account.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.usersService.delete(user)
    })
  }

  editGroup(group: PaperlessGroup) {
    var modal = this.modalService.open(GroupEditDialogComponent, {
      backdrop: 'static',
      size: 'lg',
    })
    modal.componentInstance.dialogMode = group ? 'edit' : 'create'
    modal.componentInstance.object = group
    modal.componentInstance.success
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (newGroup) => {
          this.toastService.showInfo($localize`Saved group "${newGroup.name}".`)
          this.groupsService.listAll().subscribe((r) => {
            this.groups = r.results
            this.initialize()
          })
        },
        error: (e) => {
          this.toastService.showError(
            $localize`Error saving group: ${e.toString()}.`
          )
        },
      })
  }

  deleteGroup(group: PaperlessGroup) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete user group`
    modal.componentInstance.messageBold = $localize`This operation will permanently this user group.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.groupsService.delete(group)
    })
  }
}
