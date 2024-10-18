import { Component, EventEmitter, forwardRef, input, Input, OnInit, Output } from '@angular/core'
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
@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DossierCustomFieldSelectComponent),
      multi: true,
    },
  ],
  selector: 'pngx-dossier-custom-field-select',
  templateUrl: './dossier-custom-field-select.component.html',
  styleUrls: ['./dossier-custom-field-select.component.scss'],
})
export class DossierCustomFieldSelectComponent
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
  dictCustomFields:{ [key: string]: any }={}
  dictCustomFieldsEnable: {}={}
  // form = new FormGroup({})
  form: FormGroup
  dossier: Dossier[]=[]


  typesWithAllActions: Set<string> = new Set()

  _inheritedPermissions: string[] = []
  _inheritedCustomFields: CustomFieldInstance[] = []
  dossierReference: any[]= []

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

    this.dictCustomFields={}

    this.dictCustomFieldsEnable={}
    const newInheritedCustomFields = inherited?.length? inherited: []
    this.getFields(newInheritedCustomFields);


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
    // console.log("dossier",this.inputDossier);
    // if(this.inputDossier!=undefined){
    //   this.dataDossier()
    // }
    // if(this.inputDossierForm!=undefined){

    // }

    this.customFields.valueChanges.subscribe(data => {
      const filteredData = data.filter(item => this.dictCustomFieldsEnable[item.field]);
        this.dataChange.emit(filteredData);
    });

  }


  get customFields(): FormArray {
    return this.form.get('customFields') as FormArray;
  }


  private getFields(newInheritedCustomFields) {


    this.customFieldsService.clearCache();
    this.customFieldsService
    .listAll()
    .pipe(takeUntil(this.unsubscribeNotifier))
    .subscribe((result) => {
      this.arrayCustomFields = result.results
      this.loading=true
      this.writeValue(newInheritedCustomFields)
      // console.log('gia tri',this.arrayCustomFields)
    })


  }

  dataDossier(id){
    let type = ""
    if (this.inputDossier?.type=='DOSSIER'){
      type = "DOCUMENT"
    }
    else if (this.inputDossier?.type=="DOCUMENT"){
      type="FILE"
    }
    this.dossierService.listDossierFiltered(1,null,null,null,id,null,null,type)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((c) => {
        this.dossier = c.results
      })
  }

  writeValue(newInheritedCustomFields): void {
    console.log("call",newInheritedCustomFields,)
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
          "value_reference": null,
          "value_origin": null,
          "apply": false,

        };
        this.dictCustomFieldsEnable[c.id] = false
      }else{
        this.dictCustomFields[c.id] = {
          "value": this.dictCustomFields[c.id].value,
          "field": c.id,
          "match_value": "",
          "dossier_document": null,
          "field_name": c.name,
          "reference": null,
          "value_reference": null,
          "value_origin": this.dictCustomFields[c.id].value,
          "apply": false,

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
          value_reference: new FormControl(value?.value_reference),
          value_origin: new FormControl(value?.value_origin),
          apply: new FormControl(value?.apply),
        }));

      }
      this.dossierReference.push([])
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
    if(this.inputDossier!=undefined){
      this.dataDossier(this.inputDossier.id)
    }
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

  applyClick(event,field,index) {
    if (this.customFields.at(index).get('apply').value==false){
      let fieldId = this.customFields.at(index).get('field').value
      this.dictCustomFields[fieldId]?.apply==true
      this.customFields.at(index).patchValue({value: this.customFields.at(index).get('value_reference').value})
      this.customFields.at(index).patchValue({apply: true})

    }else if(this.customFields.at(index).get('apply').value==true){
      let fieldId = this.customFields.at(index).get('field').value
      this.dictCustomFields[fieldId]?.apply==false
      this.customFields.at(index).patchValue({value: this.customFields.at(index).get('value_origin').value})
      // this.customFields.at(index).patchValue({value: this.customFields.at(index).get('value_reference').value})
      this.customFields.at(index).patchValue({apply: false})

    }
  }

  onMatchValueChange(event, field: any) {
    field.value.match_value=event.target.value

  }

  modelChangeDossier(event,i) {
    if (event!=null){
      const d = this.dossier.find(obj => obj.id === event);
      // console.log(this.dossier)
      this.dossierReference[i]=d?.custom_fields
    }
  }

  modelChangeField(event,index) {
    if (event!=null){
      const d = this.dossierReference[index].find(obj => obj.id === event);
      this.customFields.at(index).patchValue({value_reference: d?.value})

      this.dictCustomFields[this.customFields.at(index).get('field').value].value_reference = d?.value
    }
  }



}
