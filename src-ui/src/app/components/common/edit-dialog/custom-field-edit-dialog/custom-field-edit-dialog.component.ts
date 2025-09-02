import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  QueryList,
  ViewChildren,
  inject,
} from '@angular/core'
import {
  FormArray,
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { takeUntil } from 'rxjs'
import {
  CustomField,
  CustomFieldDataType,
  DATA_TYPE_LABELS,
} from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'

@Component({
  selector: 'pngx-custom-field-edit-dialog',
  templateUrl: './custom-field-edit-dialog.component.html',
  styleUrls: ['./custom-field-edit-dialog.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    SelectComponent,
    TextComponent,
    FormsModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
    NgbPaginationModule,
  ],
})
export class CustomFieldEditDialogComponent
  extends EditDialogComponent<CustomField>
  implements OnInit, AfterViewInit
{
  CustomFieldDataType = CustomFieldDataType

  @ViewChildren('selectOption')
  private selectOptionInputs: QueryList<ElementRef>

  pageSize = 25
  private _page = 1
  private allOptions: { label: string; id: string }[] = []
  private pauseFocus = false

  get page() {
    return this._page
  }
  set page(p: number) {
    this.syncBackToAllOptions()
    this._page = p
    this.rebuildPage()
  }

  get selectOptions(): FormArray {
    return this.objectForm.get('extra_data.select_options') as FormArray
  }

  constructor() {
    super()
    this.service = inject(CustomFieldsService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  ngOnInit(): void {
    super.ngOnInit()
    if (this.typeFieldDisabled) {
      this.objectForm.get('data_type')!.disable()
    }
    if (this.object?.data_type === CustomFieldDataType.Select) {
      this.allOptions = (this.object.extra_data?.select_options ?? []).filter(
        Boolean
      )
      this.page = 1
    }
  }

  ngAfterViewInit(): void {
    this.selectOptionInputs.changes
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        if (!this.pauseFocus) {
          this.selectOptionInputs.last?.nativeElement.focus()
        }
      })
  }

  getCreateTitle() {
    return $localize`Create new custom field`
  }

  getEditTitle() {
    return $localize`Edit custom field`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      data_type: new FormControl(null),
      extra_data: new FormGroup({
        select_options: new FormArray([]),
        default_currency: new FormControl(null),
      }),
    })
  }

  getDataTypes() {
    return DATA_TYPE_LABELS
  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }

  public addSelectOption() {
    this.syncBackToAllOptions()
    this.allOptions.push({ label: '', id: crypto.randomUUID() })
    this.page = Math.ceil(this.allOptions.length / this.pageSize)
  }

  public removeSelectOption(indexOnPage: number) {
    this.syncBackToAllOptions()
    const globalIndex = (this.page - 1) * this.pageSize + indexOnPage
    this.allOptions.splice(globalIndex, 1)
    const maxPage = Math.max(
      1,
      Math.ceil(this.allOptions.length / this.pageSize)
    )
    if (this.page > maxPage) {
      this._page = maxPage
    }
    this.rebuildPage()
  }

  private rebuildPage() {
    const start = (this.page - 1) * this.pageSize
    const slice = this.allOptions.slice(start, start + this.pageSize)

    this.pauseFocus = true
    this.selectOptions.clear()
    for (const o of slice) {
      this.selectOptions.push(
        new FormGroup({
          label: new FormControl(o.label, { updateOn: 'blur' }),
          id: new FormControl(o.id),
        })
      )
    }
    this.pauseFocus = false
  }

  private syncBackToAllOptions() {
    const start = (this.page - 1) * this.pageSize
    this.selectOptions.controls.forEach((fg, i) => {
      const v = fg.value as { label: string; id: string }
      this.allOptions[start + i] = v
    })
  }

  override save() {
    if (
      this.objectForm.get('data_type')!.value === CustomFieldDataType.Select
    ) {
      this.syncBackToAllOptions()
      const extra = this.objectForm.get('extra_data') as FormGroup
      const original = this.selectOptions
      extra.setControl('select_options', new FormControl(this.allOptions))
      try {
        super.save()
      } finally {
        extra.setControl('select_options', original)
        this.rebuildPage()
      }
      return
    }
    super.save()
  }
}
