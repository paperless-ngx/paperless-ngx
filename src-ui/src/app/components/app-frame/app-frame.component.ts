import {
  CdkDragDrop,
  CdkDragEnd,
  CdkDragStart,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { NgClass } from '@angular/common'
import { Component, HostListener, OnInit } from '@angular/core'
import { ActivatedRoute, Router, RouterModule } from '@angular/router'
import {
  NgbCollapseModule,
  NgbDropdownModule,
  NgbModal,
  NgbNavModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { TourNgBootstrapModule } from 'ngx-ui-tour-ng-bootstrap'
import { Observable } from 'rxjs'
import { first } from 'rxjs/operators'
import { Document } from 'src/app/data/document'
import { SavedView } from 'src/app/data/saved-view'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
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
import { ProfileEditDialogComponent } from '../common/profile-edit-dialog/profile-edit-dialog.component'
import { DocumentDetailComponent } from '../document-detail/document-detail.component'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { GlobalSearchComponent } from './global-search/global-search.component'
import { ToastsDropdownComponent } from './toasts-dropdown/toasts-dropdown.component'

@Component({
  selector: 'pngx-app-frame',
  templateUrl: './app-frame.component.html',
  styleUrls: ['./app-frame.component.scss'],
  imports: [
    GlobalSearchComponent,
    DocumentTitlePipe,
    IfPermissionsDirective,
    ToastsDropdownComponent,
    RouterModule,
    NgClass,
    NgbDropdownModule,
    NgbPopoverModule,
    NgbCollapseModule,
    NgbNavModule,
    NgxBootstrapIconsModule,
    DragDropModule,
    TourNgBootstrapModule,
  ],
})
export class AppFrameComponent
  extends ComponentWithPermissions
  implements OnInit, ComponentCanDeactivate
{
  versionString = `${environment.appTitle} ${environment.version}`
  appRemoteVersion: AppRemoteVersion

  isMenuCollapsed: boolean = true

  slimSidebarAnimating: boolean = false

  constructor(
    public router: Router,
    private activatedRoute: ActivatedRoute,
    private openDocumentsService: OpenDocumentsService,
    public savedViewService: SavedViewService,
    private remoteVersionService: RemoteVersionService,
    public settingsService: SettingsService,
    public tasksService: TasksService,
    private readonly toastService: ToastService,
    private modalService: NgbModal,
    public permissionsService: PermissionsService,
    private djangoMessagesService: DjangoMessagesService
  ) {
    super()

    if (
      permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.SavedView
      )
    ) {
      this.savedViewService.reload()
    }
  }

  ngOnInit(): void {
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
    this.slimSidebarAnimating = true
    this.slimSidebarEnabled = !this.slimSidebarEnabled
    setTimeout(() => {
      this.slimSidebarAnimating = false
    }, 200) // slightly longer than css animation for slim sidebar
  }

  get customAppTitle(): string {
    return this.settingsService.get(SETTINGS_KEYS.APP_TITLE)
  }

  get slimSidebarEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.SLIM_SIDEBAR)
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

  closeMenu() {
    this.isMenuCollapsed = true
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
    this.settingsService.globalDropzoneEnabled = false
  }

  onDragEnd(event: CdkDragEnd) {
    this.settingsService.globalDropzoneEnabled = true
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
        this.appRemoteVersion = appRemoteVersion
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
}
