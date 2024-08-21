import { Component, EventEmitter, forwardRef, Input, OnInit, Output } from '@angular/core'
import {
  ControlValueAccessor,
  FormArray,
  FormBuilder,
  FormControl,
  FormGroup,
  NG_VALUE_ACCESSOR,
} from '@angular/forms'
import { ComponentWithPermissions } from '../../../with-permissions/with-permissions.component'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { Subject, first, takeUntil } from 'rxjs'
import { CustomFieldInstance } from 'src/app/data/custom-field-instance'
import { DossierService } from 'src/app/services/rest/dossier.service'
import { Dossier, DossierType } from 'src/app/data/dossier'
import { DossierForm } from 'src/app/data/dossier-form'
import { DossierFormService } from 'src/app/services/rest/dossier-forms.service'
import { AbstractInputComponent } from '../../input/abstract-input'
@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DossierFormCustomFieldSelectComponent),
      multi: true,
    },
  ],
  selector: 'pngx-dossier-form-custom-field-select',
  templateUrl: './dossier-form-custom-field-select.component.html',
  styleUrls: ['./dossier-form-custom-field-select.component.scss'],
})
export class DossierFormCustomFieldSelectComponent
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
  dossierForm: DossierForm[]=[]


  typesWithAllActions: Set<string> = new Set()

  _inheritedPermissions: string[] = []
  _inheritedCustomFields: CustomFieldInstance[] = []
  dossierFormReference: any[] = []

  
  @Input()
  set inheritedCustomFields(inherited: CustomFieldInstance[]) {
    this.dictCustomFields={}
    this.dictCustomFieldsEnable={}
    this._inheritedCustomFields = inherited?.length? inherited: []
    // console.log("gia tri inherited",this._inheritedCustomFields)
    
  }

  @Input() inputDossier: Dossier 
  @Input() inputDossierForm: DossierForm 
  @Input() dataDossierForm: FormGroup 
  @Output() dataChange = new EventEmitter<any[]>();

  inheritedWarning: string = $localize`Inherited from dossier form`

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
    
    this.customFields.valueChanges.subscribe(data => {
      const filteredData = data.filter(item => this.dictCustomFieldsEnable[item.field]);
        this.dataChange.emit(filteredData);
    });
    console.log("gia trii inputDossierForm",this.inputDossierForm);
    
  }
  

  get customFields(): FormArray {
    return this.form.get('customFields') as FormArray;
  }
  

  private getFields(newInheritedCustomFields) {
    this.customFieldsService.clearCache()
    this.customFieldsService
    .listAll()
    .pipe(takeUntil(this.unsubscribeNotifier))
    .subscribe((result) => {
      this.arrayCustomFields = result.results
      this.writeValue(newInheritedCustomFields)
     
    })    
  }


  dataDossier(){
    this.dossierFormService
      .listDossierFormFiltered(
        1,null,null,null,null,null,true,'DOCUMENT'
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((c) => {
        this.dossierForm = c.results
        this.getFields(this._inheritedCustomFields);
      })
    
  }

  writeValue(newInheritedCustomFields): void {
    this.dictCustomFields = {};
    this.customFields.clear();
    newInheritedCustomFields.forEach((obj, index, array) => {
      this.dictCustomFields[obj.field] = obj;
      this.dictCustomFieldsEnable[obj.field] = true;
    });
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
      else if (c.id in this.dictCustomFields) {
        this.dictCustomFields[c.id] = {
          "value": null,
          "field": c.id,
          "match_value":  this.dictCustomFields[c.id].match_value,
          "dossier_document":  this.dictCustomFields[c.id].dossier_document,
          "field_name": c.name,
          "reference":  this.dictCustomFields[c.id].reference,
          
        };
        this.dictCustomFieldsEnable[c.id] = true
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

  
  onChange = (newValue: string[]) => {}

  onTouched = () => {}

  disabled: boolean = false

  registerOnChange(fn: any): void {
    this.onChange = fn
  }

  registerOnTouched(fn: any): void {
    this.onTouched = fn
  }



  ngOnInit(): void {
    if(this.inputDossierForm!=undefined){
      this.dataDossier()
    } 
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

  enableClick(event, field) {
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
  }

  modelChangeDossier(event,index) {
    if (event!=null){
      const d = this.dossierForm.find(obj => obj.id === event);
      console.log('dd',this.customFields.at(index).value);
      if (d==null){
        this.customFields.at(index).patchValue({reference: null})
      }
      return d?.custom_fields
    }
  }
  handleRemove(index): void {
    // console.log("GIA TRI",index,this.customFields.at(index).get("dossier_document").value)
    if (this.customFields.at(index).get("dossier_document").value == null){
      this.customFields.at(index).patchValue({reference: null}) 
    }
  }
  getCustomFieldOfForm(formId){
    if (formId.value!=null){
      const d = this.dossierForm.find(obj => obj.id === formId.value);
      // this.dossierFormReference =  d?.custom_fields
      return d?.custom_fields
    }

  }
  modelChangeField(event,index) {
    if (event!=null){
      const d = this.dossierFormReference.find(obj => obj.id === event);
      this.customFields.at(index).patchValue({value_reference: d?.value})      
    }

  }



}
