import {
  AfterViewInit,
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

const SELECT_OPTION_PAGE_SIZE = 8

@Component({
  selector: 'pngx-custom-field-edit-dialog',
  templateUrl: './custom-field-edit-dialog.component.html',
  styleUrls: ['./custom-field-edit-dialog.component.scss'],
  imports: [
    SelectComponent,
    TextComponent,
    FormsModule,
    ReactiveFormsModule,
    NgbPaginationModule,
    NgxBootstrapIconsModule,
  ],
})
export class CustomFieldEditDialogComponent
  extends EditDialogComponent<CustomField>
  implements OnInit, AfterViewInit
{
  CustomFieldDataType = CustomFieldDataType
  SELECT_OPTION_PAGE_SIZE = SELECT_OPTION_PAGE_SIZE

  private _allSelectOptions: any[] = []
  public get allSelectOptions(): any[] {
    return this._allSelectOptions
  }

  private _selectOptionsPage: number
  public get selectOptionsPage(): number {
    return this._selectOptionsPage
  }
  public set selectOptionsPage(v: number) {
    this._selectOptionsPage = v
    this.updateSelectOptions()
  }

  @ViewChildren('selectOption')
  private selectOptionInputs: QueryList<ElementRef>

  private get selectOptions(): FormArray {
    return (this.objectForm.controls.extra_data as FormGroup).controls
      .select_options as FormArray
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
      this.objectForm.get('data_type').disable()
    }
    if (this.object?.data_type === CustomFieldDataType.Select) {
      this._allSelectOptions = [
        ...(this.object.extra_data.select_options ?? []),
      ]
      this.selectOptionsPage = 1
    }
  }

  ngAfterViewInit(): void {
    this.selectOptionInputs.changes
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.selectOptionInputs.last?.nativeElement.focus()
      })

    this.objectForm.valueChanges
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((change) => {
        // Update the relevant select options values if changed in the form, which is only a page of the entire list
        this.objectForm
          .get('extra_data.select_options')
          ?.value.forEach((option, index) => {
            this._allSelectOptions[
              index + (this.selectOptionsPage - 1) * SELECT_OPTION_PAGE_SIZE
            ] = option
          })
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

  protected getFormValues() {
    const formValues = super.getFormValues()
    if (
      this.objectForm.get('data_type')?.value === CustomFieldDataType.Select
    ) {
      // Make sure we send all select options, with updated values
      formValues.extra_data.select_options = this._allSelectOptions
    }
    return formValues
  }

  getDataTypes() {
    return DATA_TYPE_LABELS
  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }

  private updateSelectOptions() {
    this.selectOptions.clear()
    this._allSelectOptions
      .slice(
        (this.selectOptionsPage - 1) * SELECT_OPTION_PAGE_SIZE,
        this.selectOptionsPage * SELECT_OPTION_PAGE_SIZE
      )
      .forEach((option) =>
        this.selectOptions.push(
          new FormGroup({
            label: new FormControl(option.label),
            id: new FormControl(option.id),
          })
        )
      )
  }

  public addSelectOption() {
    this._allSelectOptions.push({ label: null, id: null })
    this.selectOptionsPage = Math.ceil(
      this.allSelectOptions.length / SELECT_OPTION_PAGE_SIZE
    )
  }

  public removeSelectOption(index: number) {
    const globalIndex =
      index + (this.selectOptionsPage - 1) * SELECT_OPTION_PAGE_SIZE
    this._allSelectOptions.splice(globalIndex, 1)

    const totalPages = Math.max(
      1,
      Math.ceil(this._allSelectOptions.length / SELECT_OPTION_PAGE_SIZE)
    )
    const targetPage = Math.min(this.selectOptionsPage, totalPages)

    this.selectOptionsPage = targetPage
  }
}
