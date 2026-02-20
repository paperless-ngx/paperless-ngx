import { AsyncPipe } from '@angular/common'
import { Component, OnDestroy, OnInit, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { dirtyCheck } from '@ngneat/dirty-check-forms'
import { BehaviorSubject, Observable, takeUntil } from 'rxjs'
import { PermissionsDialogComponent } from 'src/app/components/common/permissions-dialog/permissions-dialog.component'
import { DisplayMode } from 'src/app/data/document'
import { SavedView } from 'src/app/data/saved-view'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import {
  PermissionAction,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmButtonComponent } from '../../common/confirm-button/confirm-button.component'
import { DragDropSelectComponent } from '../../common/input/drag-drop-select/drag-drop-select.component'
import { NumberComponent } from '../../common/input/number/number.component'
import { TextComponent } from '../../common/input/text/text.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
@Component({
  selector: 'pngx-saved-views',
  templateUrl: './saved-views.component.html',
  styleUrl: './saved-views.component.scss',
  imports: [
    PageHeaderComponent,
    ConfirmButtonComponent,
    NumberComponent,
    TextComponent,
    IfPermissionsDirective,
    DragDropSelectComponent,
    FormsModule,
    ReactiveFormsModule,
    AsyncPipe,
  ],
})
export class SavedViewsComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  private savedViewService = inject(SavedViewService)
  private permissionsService = inject(PermissionsService)
  private settings = inject(SettingsService)
  private toastService = inject(ToastService)
  private modalService = inject(NgbModal)

  DisplayMode = DisplayMode

  public savedViews: SavedView[]
  private savedViewsGroup = new FormGroup({})
  public savedViewsForm: FormGroup = new FormGroup({
    savedViews: this.savedViewsGroup,
  })

  private store: BehaviorSubject<any>
  public isDirty$: Observable<boolean>

  get displayFields() {
    return this.settings.allDisplayFields
  }

  constructor() {
    super()
    this.settings.organizingSidebarSavedViews = true
  }

  ngOnInit(): void {
    this.reloadViews()
  }

  ngOnDestroy(): void {
    this.settings.organizingSidebarSavedViews = false
    super.ngOnDestroy()
  }

  private initialize() {
    this.loading = false
    this.emptyGroup(this.savedViewsGroup)

    let storeData = {
      savedViews: {},
    }

    for (let view of this.savedViews) {
      storeData.savedViews[view.id.toString()] = {
        id: view.id,
        name: view.name,
        show_on_dashboard: view.show_on_dashboard,
        show_in_sidebar: view.show_in_sidebar,
        page_size: view.page_size,
        display_mode: view.display_mode,
        display_fields: view.display_fields,
      }
      const canEdit = this.canEditSavedView(view)
      this.savedViewsGroup.addControl(
        view.id.toString(),
        new FormGroup({
          id: new FormControl({ value: null, disabled: !canEdit }),
          name: new FormControl({ value: null, disabled: !canEdit }),
          show_on_dashboard: new FormControl({
            value: null,
            disabled: !canEdit,
          }),
          show_in_sidebar: new FormControl({ value: null, disabled: !canEdit }),
          page_size: new FormControl({ value: null, disabled: !canEdit }),
          display_mode: new FormControl({ value: null, disabled: !canEdit }),
          display_fields: new FormControl({ value: [], disabled: !canEdit }),
        })
      )
    }

    this.store = new BehaviorSubject(storeData)
    this.store
      .asObservable()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((state) => {
        this.savedViewsForm.patchValue(state, { emitEvent: false })
      })

    // Initialize dirtyCheck
    this.isDirty$ = dirtyCheck(this.savedViewsForm, this.store.asObservable())
  }

  public reset() {
    this.savedViewsForm.patchValue(this.store.getValue())
  }

  public deleteSavedView(savedView: SavedView) {
    if (!this.canDeleteSavedView(savedView)) {
      return
    }
    this.savedViewService.delete(savedView).subscribe(() => {
      this.savedViewsGroup.removeControl(savedView.id.toString())
      this.savedViews.splice(this.savedViews.indexOf(savedView), 1)
      this.toastService.showInfo(
        $localize`Saved view "${savedView.name}" deleted.`
      )
      this.savedViewService.clearCache()
      this.reloadViews()
    })
  }

  private emptyGroup(group: FormGroup) {
    Object.keys(group.controls).forEach((key) => group.removeControl(key))
  }

  public save() {
    // only patch views that have actually changed
    const changed: SavedView[] = []
    Object.values(this.savedViewsGroup.controls)
      .filter((g: FormGroup) => g.enabled && !g.pristine)
      .forEach((group: FormGroup) => {
        changed.push(group.getRawValue())
      })
    if (changed.length) {
      this.savedViewService.patchMany(changed).subscribe({
        next: () => {
          this.toastService.showInfo($localize`Views saved successfully.`)
          this.reloadViews()
        },
        error: (error) => {
          this.toastService.showError(
            $localize`Error while saving views.`,
            error
          )
        },
      })
    }
  }

  public canEditSavedView(view: SavedView): boolean {
    return this.permissionsService.currentUserHasObjectPermissions(
      PermissionAction.Change,
      view
    )
  }

  public canDeleteSavedView(view: SavedView): boolean {
    return this.permissionsService.currentUserOwnsObject(view)
  }

  public editPermissions(savedView: SavedView): void {
    if (!this.canDeleteSavedView(savedView)) {
      return
    }
    const modal = this.modalService.open(PermissionsDialogComponent, {
      backdrop: 'static',
    })
    const dialog = modal.componentInstance as PermissionsDialogComponent
    dialog.object = savedView

    modal.componentInstance.confirmClicked.subscribe(({ permissions }) => {
      modal.componentInstance.buttonsEnabled = false
      const view = {
        id: savedView.id,
        owner: permissions.owner,
      }
      view['set_permissions'] = permissions.set_permissions
      this.savedViewService.patch(view as SavedView).subscribe({
        next: () => {
          this.toastService.showInfo($localize`Permissions updated`)
          modal.close()
          this.reloadViews()
        },
        error: (error) => {
          this.toastService.showError(
            $localize`Error updating permissions`,
            error
          )
        },
      })
    })
  }

  private reloadViews(): void {
    this.loading = true
    this.savedViewService
      .listAll(null, null, { full_perms: true })
      .subscribe((r) => {
        this.savedViews = r.results
        this.initialize()
      })
  }
}
