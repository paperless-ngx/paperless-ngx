import { Component, EventEmitter, forwardRef, Input, OnInit, Output } from '@angular/core'
import {
  ControlValueAccessor,
  FormArray,
  FormBuilder,
  FormControl,
  FormGroup,
  NG_VALUE_ACCESSOR,
} from '@angular/forms'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { Subject, first, takeUntil } from 'rxjs'
import { CustomFieldInstance } from 'src/app/data/custom-field-instance'
import { DossierService } from 'src/app/services/rest/dossier.service'
import { Dossier, DossierType } from 'src/app/data/dossier'
import { DossierForm } from 'src/app/data/dossier-form'
import { DossierFormService } from 'src/app/services/rest/dossier-forms.service'
@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CustomFieldSelectComponent),
      multi: true,
    },
  ],
  selector: 'pngx-custom-field-select',
  templateUrl: './custom-field-select.component.html',
  styleUrls: ['./custom-field-select.component.scss'],
})
export class CustomFieldSelectComponent
  extends ComponentWithPermissions
  implements OnInit, ControlValueAccessor
{

  @Input()
  title: string = ''
  
  @Input()
  error: string

  
  private arrayCustomFields: CustomField[]=[]
  private unsubscribeNotifier: Subject<any> = new Subject()
  public unusedFields: CustomField[]
  permissions: string[]
  dataContainCustomFields: []=[]
  loading: Boolean = false
  dictCustomFields:{ [key: string]: CustomFieldInstance }={}
  dictCustomFieldsEnable: {}={}
  // form = new FormGroup({})
  form: FormGroup
  dossier: Dossier[]=[]


  typesWithAllActions: Set<string> = new Set()

  _inheritedPermissions: string[] = []
  _inheritedCustomFields: CustomFieldInstance[] = []

  // @Input()
  // set inheritedPermissions(inherited: string[]) {
  //   // remove <app_label>. from permission strings
  //   const newInheritedPermissions = inherited?.length
  //     ? inherited.map((p) => p.replace(/^\w+\./g, ''))
  //     : []

  //   if (this._inheritedPermissions !== newInheritedPermissions) {
  //     this._inheritedPermissions = newInheritedPermissions
  //     this.writeValue(this.permissions) // updates visual checks etc.
  //   }

  //   this.updateDisabledStates()
  // }
  @Input()
  set inheritedCustomFields(inherited: CustomFieldInstance[]) {
    this.loading =false
    // this.getFields()
    // remove <app_label>. from permission strings
    // console.log('load lai trang',inherited)
    this.dictCustomFields={}
    this.dictCustomFieldsEnable={}
    const newInheritedCustomFields = inherited?.length
    ? inherited
    : []
    
    if (this._inheritedCustomFields !== newInheritedCustomFields) {
      this._inheritedCustomFields = newInheritedCustomFields
      newInheritedCustomFields.forEach(obj => {
        this.dictCustomFields[obj.field] = obj;
        this.dictCustomFieldsEnable[obj.field] = true;
      }); 

    }
    this.getFields()  
  }

  @Input() inputDossier: Dossier 
  @Input() inputDossierForm: DossierForm 
  @Output() dataChange = new EventEmitter<any[]>();

  inheritedWarning: string = $localize`Inherited from dossier`

  constructor(
    private readonly customFieldsService: CustomFieldsService,
    private fb: FormBuilder,
    private readonly dossierService: DossierService,
    private readonly dossierFormService: DossierFormService,
  ) {
    super();
    this.form = this.fb.group({
      customFields: this.fb.array([])
    });
    
    this.dataDossier()

    this.customFields.valueChanges.subscribe(data => {
      console.log('gia tri refe',this.inputDossier)
      const filteredData = data.filter(item => this.dictCustomFieldsEnable[item.field]);
      
        this.dataChange.emit(filteredData);
      
      
    });
    
  }
  

  get customFields(): FormArray {
    return this.form.get('customFields') as FormArray;
  }
  

  private getFields() {
    this.customFieldsService.clearCache()
    this.customFieldsService
    .listAll()
    .pipe(takeUntil(this.unsubscribeNotifier))
    .subscribe((result) => {
      this.arrayCustomFields = result.results
      this.loading=true
      this.writeValue()
      // console.log('gia tri',this.arrayCustomFields)
    })
  
      // this.writeValueCustomField(this.arrayCustomFields)
    
  }


  dataDossier(){
    this.dossierFormService
      .listDossierFormFiltered(
        1,
        null,
        null,
        null,
        null,
        null,
        true,
        'DOCUMENT'
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((c) => {
        this.dossier = c.results
      })
    
  }

  dataDossierDocumentChange(field){
    if (field!=undefined){
      const d = this.dossier.find(obj => obj.id === field);
      return d?.custom_fields
    }
    return []
  }

  
  writeValue(): void {
    this.customFields.clear()
    
    if (this.loading==true){
      for (let c of this.arrayCustomFields) {
        if (!(c.id in this.dictCustomFields)) {
          this.dictCustomFields[c.id] = {
            "value": null,
            "field": c.id,
            "match_value": "",
            "dossier_document": null,
            "field_name": c.name,
            "reference": null,
            
          };
          this.dictCustomFieldsEnable[c.id] = false
        }
      }
      for (const [key, value] of Object.entries(this.dictCustomFields)) {
        {
          this.customFields.push(this.fb.group({
            value: new FormControl(value?.value),
            field: new FormControl(value?.field),
            match_value: new FormControl(value?.match_value),
            field_name: new FormControl(value?.field_name),
            reference: new FormControl(value?.reference),
            dossier_document: new FormControl(value?.dossier_document),
          }));
         
        }
      }
      
    }
   
    
    // this._inheritedCustomFields.push(...this.arrayCustomFields)

  }

  
  onChange = (newValue: string[]) => {}

  onTouched = () => {}

  disabled: boolean = false

  registerOnChange(fn: any): void {
    
  
    // console.log('Form values:', this.form.value)
    this.onChange = fn
  }

  registerOnTouched(fn: any): void {
    this.onTouched = fn
  }



  ngOnInit(): void {
    // this.getFields()
  }

  toggleAll(event, field) {
    if (this.dictCustomFieldsEnable[field.value]){
      this.dictCustomFieldsEnable[field.value]=false
    }
    else{
      this.dictCustomFieldsEnable[field.value]=true
    }
    const result = [];

    for (const key in this.dictCustomFields) {
      if (this.dictCustomFieldsEnable[key]) {
        result.push(this.dictCustomFields[key]);
      }
    }
    this.dataChange.emit(result);
    // this.customFields.clear()
    
    // for (const [key, value] of Object.entries(this.dictCustomFields)) {
    //   if (this.dictCustomFieldsEnable[key]==true){
    //     this.customFields.push(this.fb.group({
    //         value: new FormControl(value?.value),
    //         field: new FormControl(value?.field),
    //         match_value: new FormControl(value?.match_value),
    //         field_name: new FormControl(value?.field_name),
    //         reference: new FormControl(value?.reference),

    //     }));
       
    //   }
    // }

  }
 
  onMatchValueChange(event, field: any) {
    field.value.match_value=event.target.value
   
  }



}
