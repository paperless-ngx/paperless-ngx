import { Component, HostListener, OnInit } from '@angular/core'
import { ActivatedRoute, Router } from '@angular/router'
import { Observable } from 'rxjs'
import { first } from 'rxjs/operators'
import { Document } from 'src/app/data/document'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import {
  DjangoMessageLevel,
  DjangoMessagesService,
} from 'src/app/services/django-messages.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { environment } from 'src/environments/environment'
import { DocumentDetailComponent } from '../document-detail/document-detail.component'
import {
  RemoteVersionService,
  AppRemoteVersion,
} from 'src/app/services/rest/remote-version.service'
import { SettingsService } from 'src/app/services/settings.service'
import { TasksService } from 'src/app/services/tasks.service'
import { ComponentCanDeactivate } from 'src/app/guards/dirty-doc.guard'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { ToastService } from 'src/app/services/toast.service'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { SavedView } from 'src/app/data/saved-view'
import {
  CdkDragStart,
  CdkDragEnd,
  CdkDragDrop,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { ProfileEditDialogComponent } from '../common/profile-edit-dialog/profile-edit-dialog.component'

@Component({
  selector: 'pngx-app-frame',
  templateUrl: './app-frame.component.html',
  styleUrls: ['./app-frame.component.scss'],
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
    this.tasksService.reload()

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
