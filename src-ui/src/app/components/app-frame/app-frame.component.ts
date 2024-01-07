import { Component, HostListener, OnInit } from '@angular/core'
import { FormControl } from '@angular/forms'
import { ActivatedRoute, Router } from '@angular/router'
import { from, Observable } from 'rxjs'
import {
  debounceTime,
  distinctUntilChanged,
  map,
  switchMap,
  first,
  catchError,
} from 'rxjs/operators'
import { Document } from 'src/app/data/document'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SearchService } from 'src/app/services/rest/search.service'
import { environment } from 'src/environments/environment'
import { DocumentDetailComponent } from '../document-detail/document-detail.component'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_FULLTEXT_QUERY } from 'src/app/data/filter-rule-type'
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

  searchField = new FormControl('')

  constructor(
    public router: Router,
    private activatedRoute: ActivatedRoute,
    private openDocumentsService: OpenDocumentsService,
    private searchService: SearchService,
    public savedViewService: SavedViewService,
    private remoteVersionService: RemoteVersionService,
    private list: DocumentListViewService,
    public settingsService: SettingsService,
    public tasksService: TasksService,
    private readonly toastService: ToastService,
    private modalService: NgbModal,
    permissionsService: PermissionsService
  ) {
    super()

    if (
      permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.SavedView
      )
    ) {
      this.savedViewService.initialize()
    }
  }

  ngOnInit(): void {
    if (this.settingsService.get(SETTINGS_KEYS.UPDATE_CHECKING_ENABLED)) {
      this.checkForUpdates()
    }
    this.tasksService.reload()
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

  get searchFieldEmpty(): boolean {
    return this.searchField.value.trim().length == 0
  }

  resetSearchField() {
    this.searchField.reset('')
  }

  searchFieldKeyup(event: KeyboardEvent) {
    if (event.key == 'Escape') {
      this.resetSearchField()
    }
  }

  searchAutoComplete = (text$: Observable<string>) =>
    text$.pipe(
      debounceTime(200),
      distinctUntilChanged(),
      map((term) => {
        if (term.lastIndexOf(' ') != -1) {
          return term.substring(term.lastIndexOf(' ') + 1)
        } else {
          return term
        }
      }),
      switchMap((term) =>
        term.length < 2
          ? from([[]])
          : this.searchService.autocomplete(term).pipe(
              catchError(() => {
                return from([[]])
              })
            )
      )
    )

  itemSelected(event) {
    event.preventDefault()
    let currentSearch: string = this.searchField.value
    let lastSpaceIndex = currentSearch.lastIndexOf(' ')
    if (lastSpaceIndex != -1) {
      currentSearch = currentSearch.substring(0, lastSpaceIndex + 1)
      currentSearch += event.item + ' '
    } else {
      currentSearch = event.item + ' '
    }
    this.searchField.patchValue(currentSearch)
  }

  search() {
    this.closeMenu()
    this.list.quickFilter([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: (this.searchField.value as string).trim(),
      },
    ])
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
