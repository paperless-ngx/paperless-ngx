import { AsyncPipe } from '@angular/common'
import { Component, OnDestroy, OnInit } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { dirtyCheck } from '@ngneat/dirty-check-forms'
import { BehaviorSubject, Observable, takeUntil } from 'rxjs'
import { DisplayMode } from 'src/app/data/document'
import { SavedView } from 'src/app/data/saved-view'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
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

  constructor(
    private savedViewService: SavedViewService,
    private settings: SettingsService,
    private toastService: ToastService
  ) {
    super()
    this.settings.organizingSidebarSavedViews = true
  }

  ngOnInit(): void {
    this.loading = true
    this.savedViewService.listAll().subscribe((r) => {
      this.savedViews = r.results
      this.initialize()
    })
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
      this.savedViewsGroup.addControl(
        view.id.toString(),
        new FormGroup({
          id: new FormControl(null),
          name: new FormControl(null),
          show_on_dashboard: new FormControl(null),
          show_in_sidebar: new FormControl(null),
          page_size: new FormControl(null),
          display_mode: new FormControl(null),
          display_fields: new FormControl([]),
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
    this.savedViewService.delete(savedView).subscribe(() => {
      this.savedViewsGroup.removeControl(savedView.id.toString())
      this.savedViews.splice(this.savedViews.indexOf(savedView), 1)
      this.toastService.showInfo(
        $localize`Saved view "${savedView.name}" deleted.`
      )
      this.savedViewService.clearCache()
      this.savedViewService.listAll().subscribe((r) => {
        this.savedViews = r.results
        this.initialize()
      })
    })
  }

  private emptyGroup(group: FormGroup) {
    Object.keys(group.controls).forEach((key) => group.removeControl(key))
  }

  public save() {
    // only patch views that have actually changed
    const changed: SavedView[] = []
    Object.values(this.savedViewsGroup.controls)
      .filter((g: FormGroup) => !g.pristine)
      .forEach((group: FormGroup) => {
        changed.push(group.value)
      })
    if (changed.length) {
      this.savedViewService.patchMany(changed).subscribe({
        next: () => {
          this.toastService.showInfo($localize`Views saved successfully.`)
          this.store.next(this.savedViewsForm.value)
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
}
