import {
  CdkDragDrop,
  CdkDragEnd,
  CdkDragStart,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { NgClass } from '@angular/common'
import { Component, HostListener, inject, OnInit, signal } from '@angular/core'
import { ActivatedRoute, Router, RouterModule } from '@angular/router'
import {
  NgbCollapseModule,
  NgbDropdownModule,
  NgbModal,
  NgbNavModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { TourNgBootstrap } from 'ngx-ui-tour-ng-bootstrap'
import { Observable } from 'rxjs'
import { first } from 'rxjs/operators'
import { Document } from 'src/app/data/document'
import { SavedView } from 'src/app/data/saved-view'
import { CollapsibleSection, SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { ComponentCanDeactivate } from 'src/app/guards/dirty-doc.guard'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import {
  DjangoMessageLevel,
  DjangoMessagesService,
} from 'src/app/services/django-messages.service'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import {
  AppRemoteVersion,
  RemoteVersionService,
} from 'src/app/services/rest/remote-version.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { TasksService } from 'src/app/services/tasks.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ChatComponent } from '../chat/chat/chat.component'
import { BrandMarkComponent } from '../common/logo/brand-mark/brand-mark.component'
import { LogoComponent } from '../common/logo/logo.component'
import { ProfileEditDialogComponent } from '../common/profile-edit-dialog/profile-edit-dialog.component'
import { DocumentDetailComponent } from '../document-detail/document-detail.component'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { GlobalSearchComponent } from './global-search/global-search.component'
import { ToastsDropdownComponent } from './toasts-dropdown/toasts-dropdown.component'

const SCROLL_THRESHOLD = 16

@Component({
  selector: 'pngx-app-frame',
  templateUrl: './app-frame.component.html',
  styleUrls: ['./app-frame.component.scss'],
  imports: [
    GlobalSearchComponent,
    LogoComponent,
    BrandMarkComponent,
    DocumentTitlePipe,
    IfPermissionsDirective,
    ToastsDropdownComponent,
    ChatComponent,
    RouterModule,
    NgClass,
    NgbDropdownModule,
    NgbPopoverModule,
    NgbCollapseModule,
    NgbNavModule,
    NgxBootstrapIconsModule,
    DragDropModule,
    TourNgBootstrap,
  ],
})
export class AppFrameComponent
  extends ComponentWithPermissions
  implements OnInit, ComponentCanDeactivate
{
  router = inject(Router)
  private activatedRoute = inject(ActivatedRoute)
  private openDocumentsService = inject(OpenDocumentsService)
  savedViewService = inject(SavedViewService)
  private remoteVersionService = inject(RemoteVersionService)
  settingsService = inject(SettingsService)
  tasksService = inject(TasksService)
  private readonly toastService = inject(ToastService)
  private modalService = inject(NgbModal)
  permissionsService = inject(PermissionsService)
  private djangoMessagesService = inject(DjangoMessagesService)

  readonly appRemoteVersion = signal<AppRemoteVersion>(null)
  readonly isMenuCollapsed = signal(true)
  readonly slimSidebarAnimating = signal(false)
  readonly mobileSearchHidden = signal(false)
  private readonly versionSetting = this.settingsService.getSignal<string>(
    SETTINGS_KEYS.VERSION
  )
  private readonly appTitleSetting = this.settingsService.getSignal<string>(
    SETTINGS_KEYS.APP_TITLE
  )
  private readonly appLogoSetting = this.settingsService.getSignal<string>(
    SETTINGS_KEYS.APP_LOGO
  )
  private readonly slimSidebarSetting = this.settingsService.getSignal<boolean>(
    SETTINGS_KEYS.SLIM_SIDEBAR
  )
  private readonly attributesSectionsCollapsedSetting =
    this.settingsService.getSignal<CollapsibleSection[]>(
      SETTINGS_KEYS.ATTRIBUTES_SECTIONS_COLLAPSED
    )
  private readonly aiEnabledSetting = this.settingsService.getSignal<boolean>(
    SETTINGS_KEYS.AI_ENABLED
  )
  private readonly sidebarViewsShowCountSetting =
    this.settingsService.getSignal<boolean>(
      SETTINGS_KEYS.SIDEBAR_VIEWS_SHOW_COUNT
    )
  private lastScrollY: number = 0

  constructor() {
    super()
    const permissionsService = this.permissionsService

    if (
      permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.SavedView
      )
    ) {
      this.savedViewService.reload(() => {
        this.savedViewService.maybeRefreshDocumentCounts()
      })
    }
  }

  ngOnInit(): void {
    this.lastScrollY = window.scrollY
    this.detectClassicScrollbars()

    if (this.settingsService.get(SETTINGS_KEYS.UPDATE_CHECKING_ENABLED)) {
      this.checkForUpdates()
    }
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.PaperlessTask
      )
    ) {
      this.tasksService.reload()
    }

    this.djangoMessagesService.get().forEach((message) => {
      switch (message.level) {
        case DjangoMessageLevel.ERROR:
        case DjangoMessageLevel.WARNING:
          this.toastService.showError(message.message)
          break
        case DjangoMessageLevel.SUCCESS:
        case DjangoMessageLevel.INFO:
        case DjangoMessageLevel.DEBUG:
          this.toastService.showInfo(message.message)
          break
      }
    })
  }

  toggleSlimSidebar(): void {
    this.slimSidebarAnimating.set(true)
    const slimSidebarEnabled = !this.slimSidebarEnabled
    this.settingsService.set(SETTINGS_KEYS.SLIM_SIDEBAR, slimSidebarEnabled)
    if (slimSidebarEnabled) {
      this.settingsService.set(SETTINGS_KEYS.ATTRIBUTES_SECTIONS_COLLAPSED, [
        CollapsibleSection.ATTRIBUTES,
      ])
    }
    this.settingsService
      .storeSettings()
      .pipe(first())
      .subscribe({
        error: (error) => {
          this.toastService.showError(
            $localize`An error occurred while saving settings.`
          )
          console.warn(error)
        },
      })
    setTimeout(() => {
      this.slimSidebarAnimating.set(false)
    }, 200) // slightly longer than css animation for slim sidebar
  }

  toggleAttributesSections(event?: Event): void {
    event?.preventDefault()
    event?.stopPropagation()
    this.attributesSectionsCollapsed = !this.attributesSectionsCollapsed
  }

  toggleMenuCollapsed(): void {
    this.isMenuCollapsed.set(!this.isMenuCollapsed())
  }

  closeMobileSearch(): void {
    this.mobileSearchHidden.set(false)
  }

  setMobileSearchHidden(hidden: boolean): void {
    this.mobileSearchHidden.set(hidden)
  }

  get versionString(): string {
    return `${environment.appTitle} v${this.versionSetting()}${environment.tag === 'prod' ? '' : ` #${environment.tag}`}`
  }

  get appTitle(): string {
    return this.appTitleSetting() || environment.appTitle
  }

  get customAppTitle(): string {
    return this.appTitleSetting()
  }

  get hasCustomBranding(): boolean {
    return !!(this.appTitleSetting()?.length || this.appLogoSetting()?.length)
  }

  get customAppLogo(): string {
    const logo = this.appLogoSetting()
    return logo?.length
      ? environment.apiBaseUrl.replace(/\/api\/$/, logo)
      : null
  }

  get canSaveSettings(): boolean {
    return (
      this.permissionsService.currentUserCan(
        PermissionAction.Change,
        PermissionType.UISettings
      ) &&
      this.permissionsService.currentUserCan(
        PermissionAction.Add,
        PermissionType.UISettings
      )
    )
  }

  get canManageAttributes(): boolean {
    return (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Tag
      ) ||
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Correspondent
      ) ||
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.DocumentType
      ) ||
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.StoragePath
      ) ||
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.CustomField
      )
    )
  }

  get slimSidebarEnabled(): boolean {
    return this.slimSidebarSetting()
  }

  set slimSidebarEnabled(enabled: boolean) {
    this.settingsService.set(SETTINGS_KEYS.SLIM_SIDEBAR, enabled)
    this.settingsService
      .storeSettings()
      .pipe(first())
      .subscribe({
        error: (error) => {
          this.toastService.showError(
            $localize`An error occurred while saving settings.`
          )
          console.warn(error)
        },
      })
  }

  get slimSidebarPopoversEnabled(): boolean {
    return this.slimSidebarEnabled && !this.isMobileViewport()
  }

  get attributesSectionsCollapsed(): boolean {
    return this.attributesSectionsCollapsedSetting()?.includes(
      CollapsibleSection.ATTRIBUTES
    )
  }

  set attributesSectionsCollapsed(collapsed: boolean) {
    // TODO: refactor to be able to toggle individual sections, if implemented
    this.settingsService.set(
      SETTINGS_KEYS.ATTRIBUTES_SECTIONS_COLLAPSED,
      collapsed ? [CollapsibleSection.ATTRIBUTES] : []
    )
    this.settingsService
      .storeSettings()
      .pipe(first())
      .subscribe({
        error: (error) => {
          this.toastService.showError(
            $localize`An error occurred while saving settings.`
          )
          console.warn(error)
        },
      })
  }

  get aiEnabled(): boolean {
    return this.aiEnabledSetting()
  }

  @HostListener('window:resize')
  onWindowResize(): void {
    if (!this.isMobileViewport()) {
      this.mobileSearchHidden.set(false)
    }
  }

  @HostListener('window:scroll')
  onWindowScroll(): void {
    const currentScrollY = window.scrollY

    if (!this.isMobileViewport() || this.isMenuCollapsed() === false) {
      this.mobileSearchHidden.set(false)
      this.lastScrollY = currentScrollY
      return
    }

    const delta = currentScrollY - this.lastScrollY

    if (currentScrollY <= 0 || delta < -SCROLL_THRESHOLD) {
      this.mobileSearchHidden.set(false)
    } else if (currentScrollY > SCROLL_THRESHOLD && delta > SCROLL_THRESHOLD) {
      this.mobileSearchHidden.set(true)
    }

    this.lastScrollY = currentScrollY
  }

  /**
   * Flag for browsers whose scrollbars take up layout width. Remove me
   * some day, I hope.
   */
  private detectClassicScrollbars(): void {
    const probe = document.createElement('div')
    probe.style.cssText =
      'position:absolute;top:-9999px;width:100px;height:100px;overflow:scroll'
    document.body.appendChild(probe)
    document.documentElement.classList.toggle(
      'pngx-classic-scrollbars',
      probe.offsetWidth > probe.clientWidth
    )
    probe.remove()
  }

  private isMobileViewport(): boolean {
    return window.innerWidth < 768
  }

  closeMenu() {
    this.isMenuCollapsed.set(true)
  }

  editProfile() {
    this.modalService.open(ProfileEditDialogComponent, {
      backdrop: 'static',
      size: 'xl',
    })
    this.closeMenu()
  }

  get openDocuments(): Document[] {
    return this.openDocumentsService.getOpenDocuments()
  }

  @HostListener('window:beforeunload')
  canDeactivate(): Observable<boolean> | boolean {
    return !this.openDocumentsService.hasDirty()
  }

  closeDocument(d: Document) {
    this.openDocumentsService
      .closeDocument(d)
      .pipe(first())
      .subscribe((confirmed) => {
        if (confirmed) {
          this.closeMenu()
          let route = this.activatedRoute.snapshot
          while (route.firstChild) {
            route = route.firstChild
          }
          if (
            route.component == DocumentDetailComponent &&
            route.params['id'] == d.id
          ) {
            this.router.navigate([''])
          }
        }
      })
  }

  closeAll() {
    // user may need to confirm losing unsaved changes
    this.openDocumentsService
      .closeAll()
      .pipe(first())
      .subscribe((confirmed) => {
        if (confirmed) {
          this.closeMenu()

          // TODO: is there a better way to do this?
          let route = this.activatedRoute
          while (route.firstChild) {
            route = route.firstChild
          }
          if (route.component === DocumentDetailComponent) {
            this.router.navigate([''])
          }
        }
      })
  }

  onDragStart(event: CdkDragStart) {
    this.settingsService.globalDropzoneEnabled.set(false)
  }

  onDragEnd(event: CdkDragEnd) {
    this.settingsService.globalDropzoneEnabled.set(true)
  }

  onDrop(event: CdkDragDrop<SavedView[]>) {
    const sidebarViews = this.savedViewService.sidebarViews.concat([])
    moveItemInArray(sidebarViews, event.previousIndex, event.currentIndex)

    this.settingsService.updateSidebarViewsSort(sidebarViews).subscribe({
      next: () => {
        this.toastService.showInfo($localize`Sidebar views updated`)
      },
      error: (e) => {
        this.toastService.showError($localize`Error updating sidebar views`, e)
      },
    })
  }

  private checkForUpdates() {
    this.remoteVersionService
      .checkForUpdates()
      .subscribe((appRemoteVersion: AppRemoteVersion) => {
        this.appRemoteVersion.set(appRemoteVersion)
      })
  }

  setUpdateChecking(enable: boolean) {
    this.settingsService.set(SETTINGS_KEYS.UPDATE_CHECKING_ENABLED, enable)
    this.settingsService
      .storeSettings()
      .pipe(first())
      .subscribe({
        error: (error) => {
          this.toastService.showError(
            $localize`An error occurred while saving update checking settings.`
          )
          console.warn(error)
        },
      })
    if (enable) {
      this.checkForUpdates()
    }
  }

  onLogout() {
    this.openDocumentsService.closeAll()
  }

  get showSidebarCounts(): boolean {
    return (
      this.sidebarViewsShowCountSetting() &&
      !this.settingsService.organizingSidebarSavedViews()
    )
  }
}
