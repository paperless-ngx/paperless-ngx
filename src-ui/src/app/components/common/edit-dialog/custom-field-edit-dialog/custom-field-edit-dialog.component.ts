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
  imports: [
    SelectComponent,
    TextComponent,
    FormsModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
  ],
})
export class CustomFieldEditDialogComponent
  extends EditDialogComponent<CustomField>
  implements OnInit, AfterViewInit
{
  CustomFieldDataType = CustomFieldDataType

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
      this.selectOptions.clear()
      this.object.extra_data.select_options
        .filter((option) => option)
        .forEach((option) =>
          this.selectOptions.push(
            new FormGroup({
              label: new FormControl(option.label),
              id: new FormControl(option.id),
            })
          )
        )
    }
  }

  ngAfterViewInit(): void {
    this.selectOptionInputs.changes
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.selectOptionInputs.last?.nativeElement.focus()
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
    this.selectOptions.push(
      new FormGroup({ label: new FormControl(null), id: new FormControl(null) })
    )
  }

  public removeSelectOption(index: number) {
    this.selectOptions.removeAt(index)
  }
}
