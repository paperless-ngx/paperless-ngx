import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { NgTemplateOutlet } from '@angular/common'
import { Component, OnInit, inject } from '@angular/core'
import {
  AbstractControl,
  FormArray,
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbAccordionModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription, first, takeUntil } from 'rxjs'
import { Correspondent } from 'src/app/data/correspondent'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { DocumentType } from 'src/app/data/document-type'
import { MailRule } from 'src/app/data/mail-rule'
import {
  MATCHING_ALGORITHMS,
  MATCH_AUTO,
  MATCH_NONE,
} from 'src/app/data/matching-model'
import { StoragePath } from 'src/app/data/storage-path'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { Workflow } from 'src/app/data/workflow'
import {
  WorkflowAction,
  WorkflowActionType,
} from 'src/app/data/workflow-action'
import {
  DocumentSource,
  ScheduleDateField,
  WorkflowTrigger,
  WorkflowTriggerType,
} from 'src/app/data/workflow-trigger'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'
import { WorkflowService } from 'src/app/services/rest/workflow.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CustomFieldQueryExpression } from 'src/app/utils/custom-field-query-element'
import { ConfirmButtonComponent } from '../../confirm-button/confirm-button.component'
import {
  CustomFieldQueriesModel,
  CustomFieldsQueryDropdownComponent,
} from '../../custom-fields-query-dropdown/custom-fields-query-dropdown.component'
import { CheckComponent } from '../../input/check/check.component'
import { CustomFieldsValuesComponent } from '../../input/custom-fields-values/custom-fields-values.component'
import { EntriesComponent } from '../../input/entries/entries.component'
import { NumberComponent } from '../../input/number/number.component'
import { PermissionsGroupComponent } from '../../input/permissions/permissions-group/permissions-group.component'
import { PermissionsUserComponent } from '../../input/permissions/permissions-user/permissions-user.component'
import { SelectComponent } from '../../input/select/select.component'
import { SwitchComponent } from '../../input/switch/switch.component'
import { TagsComponent } from '../../input/tags/tags.component'
import { TextComponent } from '../../input/text/text.component'
import { TextAreaComponent } from '../../input/textarea/textarea.component'
import { EditDialogComponent } from '../edit-dialog.component'

export const DOCUMENT_SOURCE_OPTIONS = [
  {
    id: DocumentSource.ConsumeFolder,
    name: $localize`Consume Folder`,
  },
  {
    id: DocumentSource.ApiUpload,
    name: $localize`API Upload`,
  },
  {
    id: DocumentSource.MailFetch,
    name: $localize`Mail Fetch`,
  },
  {
    id: DocumentSource.WebUI,
    name: $localize`Web UI`,
  },
]

export const SCHEDULE_DATE_FIELD_OPTIONS = [
  {
    id: ScheduleDateField.Added,
    name: $localize`Added`,
  },
  {
    id: ScheduleDateField.Created,
    name: $localize`Created`,
  },
  {
    id: ScheduleDateField.Modified,
    name: $localize`Modified`,
  },
  {
    id: ScheduleDateField.CustomField,
    name: $localize`Custom Field`,
  },
]

export const WORKFLOW_TYPE_OPTIONS = [
  {
    id: WorkflowTriggerType.Consumption,
    name: $localize`Consumption Started`,
  },
  {
    id: WorkflowTriggerType.DocumentAdded,
    name: $localize`Document Added`,
  },
  {
    id: WorkflowTriggerType.DocumentUpdated,
    name: $localize`Document Updated`,
  },
  {
    id: WorkflowTriggerType.Scheduled,
    name: $localize`Scheduled`,
  },
]

export const WORKFLOW_ACTION_OPTIONS = [
  {
    id: WorkflowActionType.Assignment,
    name: $localize`Assignment`,
  },
  {
    id: WorkflowActionType.Removal,
    name: $localize`Removal`,
  },
  {
    id: WorkflowActionType.Email,
    name: $localize`Email`,
  },
  {
    id: WorkflowActionType.Webhook,
    name: $localize`Webhook`,
  },
  {
    id: WorkflowActionType.PasswordRemoval,
    name: $localize`Password removal`,
  },
]

export enum TriggerFilterType {
  TagsAny = 'tags_any',
  TagsAll = 'tags_all',
  TagsNone = 'tags_none',
  CorrespondentAny = 'correspondent_any',
  CorrespondentIs = 'correspondent_is',
  CorrespondentNot = 'correspondent_not',
  DocumentTypeAny = 'document_type_any',
  DocumentTypeIs = 'document_type_is',
  DocumentTypeNot = 'document_type_not',
  StoragePathAny = 'storage_path_any',
  StoragePathIs = 'storage_path_is',
  StoragePathNot = 'storage_path_not',
  CustomFieldQuery = 'custom_field_query',
}

interface TriggerFilterDefinition {
  id: TriggerFilterType
  name: string
  inputType: 'tags' | 'select' | 'customFieldQuery'
  allowMultipleEntries: boolean
  allowMultipleValues: boolean
  selectItems?: 'correspondents' | 'documentTypes' | 'storagePaths'
  disabled?: boolean
}

type TriggerFilterOption = TriggerFilterDefinition & {
  disabled?: boolean
}

type TriggerFilterAggregate = {
  filter_has_tags: number[]
  filter_has_all_tags: number[]
  filter_has_not_tags: number[]
  filter_has_any_correspondents: number[]
  filter_has_not_correspondents: number[]
  filter_has_any_document_types: number[]
  filter_has_not_document_types: number[]
  filter_has_any_storage_paths: number[]
  filter_has_not_storage_paths: number[]
  filter_has_correspondent: number | null
  filter_has_document_type: number | null
  filter_has_storage_path: number | null
  filter_custom_field_query: string | null
}

interface FilterHandler {
  apply: (aggregate: TriggerFilterAggregate, values: any) => void
  extract: (trigger: WorkflowTrigger) => any
  hasValue: (value: any) => boolean
}

const CUSTOM_FIELD_QUERY_MODEL_KEY = Symbol('customFieldQueryModel')
const CUSTOM_FIELD_QUERY_SUBSCRIPTION_KEY = Symbol(
  'customFieldQuerySubscription'
)

type CustomFieldFilterGroup = FormGroup & {
  [CUSTOM_FIELD_QUERY_MODEL_KEY]?: CustomFieldQueriesModel
  [CUSTOM_FIELD_QUERY_SUBSCRIPTION_KEY]?: Subscription
}

const TRIGGER_FILTER_DEFINITIONS: TriggerFilterDefinition[] = [
  {
    id: TriggerFilterType.TagsAny,
    name: $localize`Has any of these tags`,
    inputType: 'tags',
    allowMultipleEntries: false,
    allowMultipleValues: true,
  },
  {
    id: TriggerFilterType.TagsAll,
    name: $localize`Has all of these tags`,
    inputType: 'tags',
    allowMultipleEntries: false,
    allowMultipleValues: true,
  },
  {
    id: TriggerFilterType.TagsNone,
    name: $localize`Does not have these tags`,
    inputType: 'tags',
    allowMultipleEntries: false,
    allowMultipleValues: true,
  },
  {
    id: TriggerFilterType.CorrespondentAny,
    name: $localize`Has any of these correspondents`,
    inputType: 'select',
    allowMultipleEntries: false,
    allowMultipleValues: true,
    selectItems: 'correspondents',
  },
  {
    id: TriggerFilterType.CorrespondentIs,
    name: $localize`Has correspondent`,
    inputType: 'select',
    allowMultipleEntries: false,
    allowMultipleValues: false,
    selectItems: 'correspondents',
  },
  {
    id: TriggerFilterType.CorrespondentNot,
    name: $localize`Does not have correspondents`,
    inputType: 'select',
    allowMultipleEntries: false,
    allowMultipleValues: true,
    selectItems: 'correspondents',
  },
  {
    id: TriggerFilterType.DocumentTypeIs,
    name: $localize`Has document type`,
    inputType: 'select',
    allowMultipleEntries: false,
    allowMultipleValues: false,
    selectItems: 'documentTypes',
  },
  {
    id: TriggerFilterType.DocumentTypeAny,
    name: $localize`Has any of these document types`,
    inputType: 'select',
    allowMultipleEntries: false,
    allowMultipleValues: true,
    selectItems: 'documentTypes',
  },
  {
    id: TriggerFilterType.DocumentTypeNot,
    name: $localize`Does not have document types`,
    inputType: 'select',
    allowMultipleEntries: false,
    allowMultipleValues: true,
    selectItems: 'documentTypes',
  },
  {
    id: TriggerFilterType.StoragePathIs,
    name: $localize`Has storage path`,
    inputType: 'select',
    allowMultipleEntries: false,
    allowMultipleValues: false,
    selectItems: 'storagePaths',
  },
  {
    id: TriggerFilterType.StoragePathAny,
    name: $localize`Has any of these storage paths`,
    inputType: 'select',
    allowMultipleEntries: false,
    allowMultipleValues: true,
    selectItems: 'storagePaths',
  },
  {
    id: TriggerFilterType.StoragePathNot,
    name: $localize`Does not have storage paths`,
    inputType: 'select',
    allowMultipleEntries: false,
    allowMultipleValues: true,
    selectItems: 'storagePaths',
  },
  {
    id: TriggerFilterType.CustomFieldQuery,
    name: $localize`Matches custom field query`,
    inputType: 'customFieldQuery',
    allowMultipleEntries: false,
    allowMultipleValues: false,
  },
]

const TRIGGER_MATCHING_ALGORITHMS = MATCHING_ALGORITHMS.filter(
  (a) => a.id !== MATCH_AUTO
)

const FILTER_HANDLERS: Record<TriggerFilterType, FilterHandler> = {
  [TriggerFilterType.TagsAny]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_tags = Array.isArray(values) ? [...values] : [values]
    },
    extract: (trigger) => trigger.filter_has_tags,
    hasValue: (value) => Array.isArray(value) && value.length > 0,
  },
  [TriggerFilterType.TagsAll]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_all_tags = Array.isArray(values)
        ? [...values]
        : [values]
    },
    extract: (trigger) => trigger.filter_has_all_tags,
    hasValue: (value) => Array.isArray(value) && value.length > 0,
  },
  [TriggerFilterType.TagsNone]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_not_tags = Array.isArray(values)
        ? [...values]
        : [values]
    },
    extract: (trigger) => trigger.filter_has_not_tags,
    hasValue: (value) => Array.isArray(value) && value.length > 0,
  },
  [TriggerFilterType.CorrespondentAny]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_any_correspondents = Array.isArray(values)
        ? [...values]
        : [values]
    },
    extract: (trigger) => trigger.filter_has_any_correspondents,
    hasValue: (value) => Array.isArray(value) && value.length > 0,
  },
  [TriggerFilterType.CorrespondentIs]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_correspondent = Array.isArray(values)
        ? (values[0] ?? null)
        : values
    },
    extract: (trigger) => trigger.filter_has_correspondent,
    hasValue: (value) => value !== null && value !== undefined,
  },
  [TriggerFilterType.CorrespondentNot]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_not_correspondents = Array.isArray(values)
        ? [...values]
        : [values]
    },
    extract: (trigger) => trigger.filter_has_not_correspondents,
    hasValue: (value) => Array.isArray(value) && value.length > 0,
  },
  [TriggerFilterType.DocumentTypeIs]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_document_type = Array.isArray(values)
        ? (values[0] ?? null)
        : values
    },
    extract: (trigger) => trigger.filter_has_document_type,
    hasValue: (value) => value !== null && value !== undefined,
  },
  [TriggerFilterType.DocumentTypeAny]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_any_document_types = Array.isArray(values)
        ? [...values]
        : [values]
    },
    extract: (trigger) => trigger.filter_has_any_document_types,
    hasValue: (value) => Array.isArray(value) && value.length > 0,
  },
  [TriggerFilterType.DocumentTypeNot]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_not_document_types = Array.isArray(values)
        ? [...values]
        : [values]
    },
    extract: (trigger) => trigger.filter_has_not_document_types,
    hasValue: (value) => Array.isArray(value) && value.length > 0,
  },
  [TriggerFilterType.StoragePathIs]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_storage_path = Array.isArray(values)
        ? (values[0] ?? null)
        : values
    },
    extract: (trigger) => trigger.filter_has_storage_path,
    hasValue: (value) => value !== null && value !== undefined,
  },
  [TriggerFilterType.StoragePathAny]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_any_storage_paths = Array.isArray(values)
        ? [...values]
        : [values]
    },
    extract: (trigger) => trigger.filter_has_any_storage_paths,
    hasValue: (value) => Array.isArray(value) && value.length > 0,
  },
  [TriggerFilterType.StoragePathNot]: {
    apply: (aggregate, values) => {
      aggregate.filter_has_not_storage_paths = Array.isArray(values)
        ? [...values]
        : [values]
    },
    extract: (trigger) => trigger.filter_has_not_storage_paths,
    hasValue: (value) => Array.isArray(value) && value.length > 0,
  },
  [TriggerFilterType.CustomFieldQuery]: {
    apply: (aggregate, values) => {
      aggregate.filter_custom_field_query = values as string
    },
    extract: (trigger) => trigger.filter_custom_field_query,
    hasValue: (value) =>
      typeof value === 'string' && value !== null && value.trim().length > 0,
  },
}

@Component({
  selector: 'pngx-workflow-edit-dialog',
  templateUrl: './workflow-edit-dialog.component.html',
  styleUrls: ['./workflow-edit-dialog.component.scss'],
  imports: [
    CheckComponent,
    EntriesComponent,
    SwitchComponent,
    NumberComponent,
    TextComponent,
    SelectComponent,
    TextAreaComponent,
    TagsComponent,
    CustomFieldsValuesComponent,
    CustomFieldsQueryDropdownComponent,
    PermissionsGroupComponent,
    PermissionsUserComponent,
    ConfirmButtonComponent,
    FormsModule,
    ReactiveFormsModule,
    NgbAccordionModule,
    NgTemplateOutlet,
    DragDropModule,
    NgxBootstrapIconsModule,
  ],
})
export class WorkflowEditDialogComponent
  extends EditDialogComponent<Workflow>
  implements OnInit
{
  public WorkflowTriggerType = WorkflowTriggerType
  public WorkflowActionType = WorkflowActionType
  public TriggerFilterType = TriggerFilterType
  public filterDefinitions = TRIGGER_FILTER_DEFINITIONS

  private correspondentService: CorrespondentService
  private documentTypeService: DocumentTypeService
  private storagePathService: StoragePathService
  private mailRuleService: MailRuleService
  private customFieldsService: CustomFieldsService

  templates: Workflow[]
  correspondents: Correspondent[]
  documentTypes: DocumentType[]
  storagePaths: StoragePath[]
  mailRules: MailRule[]
  customFields: CustomField[]
  dateCustomFields: CustomField[]

  expandedItem: number = null

  private allowedActionTypes = []

  private readonly triggerFilterOptionsMap = new WeakMap<
    FormArray,
    TriggerFilterOption[]
  >()

  constructor() {
    super()
    this.service = inject(WorkflowService)
    this.correspondentService = inject(CorrespondentService)
    this.documentTypeService = inject(DocumentTypeService)
    this.storagePathService = inject(StoragePathService)
    this.mailRuleService = inject(MailRuleService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
    this.customFieldsService = inject(CustomFieldsService)

    this.correspondentService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.correspondents = result.results))

    this.documentTypeService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.documentTypes = result.results))

    this.storagePathService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.storagePaths = result.results))

    this.mailRuleService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.mailRules = result.results))

    this.customFieldsService
      .listAll()
      .pipe(first())
      .subscribe((result) => {
        this.customFields = result.results
        this.dateCustomFields = this.customFields?.filter(
          (f) => f.data_type === CustomFieldDataType.Date
        )
      })
  }

  getCreateTitle() {
    return $localize`Create new workflow`
  }

  getEditTitle() {
    return $localize`Edit workflow`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      order: new FormControl(null),
      enabled: new FormControl(true),
      triggers: new FormArray([]),
      actions: new FormArray([]),
    })
  }

  getMatchingAlgorithms() {
    // No auto matching
    return TRIGGER_MATCHING_ALGORITHMS
  }

  ngOnInit(): void {
    super.ngOnInit()
    this.updateAllTriggerActionFields()
    this.objectForm.valueChanges.subscribe(
      this.checkRemovalActionFields.bind(this)
    )
    this.checkRemovalActionFields(this.objectForm.value)
    this.allowedActionTypes = this.settingsService.get(
      SETTINGS_KEYS.EMAIL_ENABLED
    )
      ? WORKFLOW_ACTION_OPTIONS
      : WORKFLOW_ACTION_OPTIONS.filter((a) => a.id !== WorkflowActionType.Email)
  }

  private checkRemovalActionFields(formWorkflow: Workflow) {
    formWorkflow.actions
      .filter((action) => action.type === WorkflowActionType.Removal)
      .forEach((action, i) => {
        if (action.remove_all_tags) {
          this.actionFields
            .at(i)
            .get('remove_tags')
            .disable({ emitEvent: false })
        } else {
          this.actionFields
            .at(i)
            .get('remove_tags')
            .enable({ emitEvent: false })
        }

        if (action.remove_all_document_types) {
          this.actionFields
            .at(i)
            .get('remove_document_types')
            .disable({ emitEvent: false })
        } else {
          this.actionFields
            .at(i)
            .get('remove_document_types')
            .enable({ emitEvent: false })
        }

        if (action.remove_all_correspondents) {
          this.actionFields
            .at(i)
            .get('remove_correspondents')
            .disable({ emitEvent: false })
        } else {
          this.actionFields
            .at(i)
            .get('remove_correspondents')
            .enable({ emitEvent: false })
        }

        if (action.remove_all_storage_paths) {
          this.actionFields
            .at(i)
            .get('remove_storage_paths')
            .disable({ emitEvent: false })
        } else {
          this.actionFields
            .at(i)
            .get('remove_storage_paths')
            .enable({ emitEvent: false })
        }

        if (action.remove_all_custom_fields) {
          this.actionFields
            .at(i)
            .get('remove_custom_fields')
            .disable({ emitEvent: false })
        } else {
          this.actionFields
            .at(i)
            .get('remove_custom_fields')
            .enable({ emitEvent: false })
        }

        if (action.remove_all_owners) {
          this.actionFields
            .at(i)
            .get('remove_owners')
            .disable({ emitEvent: false })
        } else {
          this.actionFields
            .at(i)
            .get('remove_owners')
            .enable({ emitEvent: false })
        }

        if (action.remove_all_permissions) {
          this.actionFields
            .at(i)
            .get('remove_view_users')
            .disable({ emitEvent: false })
          this.actionFields
            .at(i)
            .get('remove_view_groups')
            .disable({ emitEvent: false })
          this.actionFields
            .at(i)
            .get('remove_change_users')
            .disable({ emitEvent: false })
          this.actionFields
            .at(i)
            .get('remove_change_groups')
            .disable({ emitEvent: false })
        } else {
          this.actionFields
            .at(i)
            .get('remove_view_users')
            .enable({ emitEvent: false })
          this.actionFields
            .at(i)
            .get('remove_view_groups')
            .enable({ emitEvent: false })
          this.actionFields
            .at(i)
            .get('remove_change_users')
            .enable({ emitEvent: false })
          this.actionFields
            .at(i)
            .get('remove_change_groups')
            .enable({ emitEvent: false })
        }
      })
  }

  get triggerFields(): FormArray {
    return this.objectForm.get('triggers') as FormArray
  }

  get actionFields(): FormArray {
    return this.objectForm.get('actions') as FormArray
  }

  protected override getFormValues(): any {
    const formValues = super.getFormValues()

    if (formValues?.triggers?.length) {
      formValues.triggers = formValues.triggers.map(
        (trigger: any, index: number) => {
          const triggerFormGroup = this.triggerFields.at(index) as FormGroup
          const filters = this.getFiltersFormArray(triggerFormGroup)

          const aggregate: TriggerFilterAggregate = {
            filter_has_tags: [],
            filter_has_all_tags: [],
            filter_has_not_tags: [],
            filter_has_any_correspondents: [],
            filter_has_not_correspondents: [],
            filter_has_any_document_types: [],
            filter_has_not_document_types: [],
            filter_has_any_storage_paths: [],
            filter_has_not_storage_paths: [],
            filter_has_correspondent: null,
            filter_has_document_type: null,
            filter_has_storage_path: null,
            filter_custom_field_query: null,
          }

          for (const control of filters.controls) {
            const type = control.get('type').value as TriggerFilterType
            const values = control.get('values').value

            if (values === null || values === undefined) {
              continue
            }

            if (Array.isArray(values) && values.length === 0) {
              continue
            }

            const handler = FILTER_HANDLERS[type]
            handler?.apply(aggregate, values)
          }

          trigger.filter_has_tags = aggregate.filter_has_tags
          trigger.filter_has_all_tags = aggregate.filter_has_all_tags
          trigger.filter_has_not_tags = aggregate.filter_has_not_tags
          trigger.filter_has_any_correspondents =
            aggregate.filter_has_any_correspondents
          trigger.filter_has_not_correspondents =
            aggregate.filter_has_not_correspondents
          trigger.filter_has_any_document_types =
            aggregate.filter_has_any_document_types
          trigger.filter_has_not_document_types =
            aggregate.filter_has_not_document_types
          trigger.filter_has_any_storage_paths =
            aggregate.filter_has_any_storage_paths
          trigger.filter_has_not_storage_paths =
            aggregate.filter_has_not_storage_paths
          trigger.filter_has_correspondent =
            aggregate.filter_has_correspondent ?? null
          trigger.filter_has_document_type =
            aggregate.filter_has_document_type ?? null
          trigger.filter_has_storage_path =
            aggregate.filter_has_storage_path ?? null
          trigger.filter_custom_field_query =
            aggregate.filter_custom_field_query ?? null

          delete trigger.filters

          return trigger
        }
      )
    }

    return formValues
  }

  public matchingPatternRequired(formGroup: FormGroup): boolean {
    return formGroup.get('matching_algorithm').value !== MATCH_NONE
  }

  private createFilterFormGroup(
    type: TriggerFilterType,
    initialValue?: any
  ): FormGroup {
    const group = new FormGroup({
      type: new FormControl(type),
      values: new FormControl(this.normalizeFilterValue(type, initialValue)),
    })

    group.get('type').valueChanges.subscribe((newType: TriggerFilterType) => {
      if (newType === TriggerFilterType.CustomFieldQuery) {
        this.ensureCustomFieldQueryModel(group)
      } else {
        this.clearCustomFieldQueryModel(group)
        group.get('values').setValue(this.getDefaultFilterValue(newType), {
          emitEvent: false,
        })
      }
    })

    if (type === TriggerFilterType.CustomFieldQuery) {
      this.ensureCustomFieldQueryModel(group, initialValue)
    }

    return group
  }

  private buildFiltersFormArray(trigger: WorkflowTrigger): FormArray {
    const filters = new FormArray([])

    for (const definition of this.filterDefinitions) {
      const handler = FILTER_HANDLERS[definition.id]
      if (!handler) {
        continue
      }

      const value = handler.extract(trigger)
      if (!handler.hasValue(value)) {
        continue
      }

      filters.push(this.createFilterFormGroup(definition.id, value))
    }

    return filters
  }

  getFiltersFormArray(formGroup: FormGroup): FormArray {
    return formGroup.get('filters') as FormArray
  }

  getFilterTypeOptions(formGroup: FormGroup, filterIndex: number) {
    const filters = this.getFiltersFormArray(formGroup)
    const options = this.getFilterTypeOptionsForArray(filters)
    const currentType = filters.at(filterIndex).get('type')
      .value as TriggerFilterType
    const usedTypes = new Set(
      filters.controls.map(
        (control) => control.get('type').value as TriggerFilterType
      )
    )

    for (const option of options) {
      if (option.allowMultipleEntries) {
        option.disabled = false
        continue
      }

      option.disabled = usedTypes.has(option.id) && option.id !== currentType
    }

    return options
  }

  canAddFilter(formGroup: FormGroup): boolean {
    const filters = this.getFiltersFormArray(formGroup)
    const usedTypes = new Set(
      filters.controls.map(
        (control) => control.get('type').value as TriggerFilterType
      )
    )

    return this.filterDefinitions.some((definition) => {
      if (definition.allowMultipleEntries) {
        return true
      }
      return !usedTypes.has(definition.id)
    })
  }

  addFilter(triggerFormGroup: FormGroup): FormGroup | null {
    const triggerIndex = this.triggerFields.controls.indexOf(triggerFormGroup)
    if (triggerIndex === -1) {
      return null
    }

    const filters = this.getFiltersFormArray(triggerFormGroup)

    const availableDefinition = this.filterDefinitions.find((definition) => {
      if (definition.allowMultipleEntries) {
        return true
      }
      return !filters.controls.some(
        (control) => control.get('type').value === definition.id
      )
    })

    if (!availableDefinition) {
      return null
    }

    filters.push(this.createFilterFormGroup(availableDefinition.id))
    triggerFormGroup.markAsDirty()
    triggerFormGroup.markAsTouched()

    return filters.at(-1) as FormGroup
  }

  removeFilter(triggerFormGroup: FormGroup, filterIndex: number) {
    const triggerIndex = this.triggerFields.controls.indexOf(triggerFormGroup)
    if (triggerIndex === -1) {
      return
    }

    const filters = this.getFiltersFormArray(triggerFormGroup)
    const filterGroup = filters.at(filterIndex) as FormGroup
    if (filterGroup?.get('type').value === TriggerFilterType.CustomFieldQuery) {
      this.clearCustomFieldQueryModel(filterGroup)
    }
    filters.removeAt(filterIndex)
    triggerFormGroup.markAsDirty()
    triggerFormGroup.markAsTouched()
  }

  getFilterDefinition(
    type: TriggerFilterType
  ): TriggerFilterDefinition | undefined {
    return this.filterDefinitions.find((definition) => definition.id === type)
  }

  getFilterName(type: TriggerFilterType): string {
    return this.getFilterDefinition(type)?.name ?? ''
  }

  isTagsFilter(type: TriggerFilterType): boolean {
    return this.getFilterDefinition(type)?.inputType === 'tags'
  }

  isCustomFieldQueryFilter(type: TriggerFilterType): boolean {
    return this.getFilterDefinition(type)?.inputType === 'customFieldQuery'
  }

  isMultiValueFilter(type: TriggerFilterType): boolean {
    switch (type) {
      case TriggerFilterType.TagsAny:
      case TriggerFilterType.TagsAll:
      case TriggerFilterType.TagsNone:
      case TriggerFilterType.CorrespondentAny:
      case TriggerFilterType.CorrespondentNot:
      case TriggerFilterType.DocumentTypeAny:
      case TriggerFilterType.DocumentTypeNot:
      case TriggerFilterType.StoragePathAny:
      case TriggerFilterType.StoragePathNot:
        return true
      default:
        return false
    }
  }

  isSelectMultiple(type: TriggerFilterType): boolean {
    return !this.isTagsFilter(type) && this.isMultiValueFilter(type)
  }

  getFilterSelectItems(type: TriggerFilterType) {
    const definition = this.getFilterDefinition(type)
    if (!definition || definition.inputType !== 'select') {
      return []
    }

    switch (definition.selectItems) {
      case 'correspondents':
        return this.correspondents
      case 'documentTypes':
        return this.documentTypes
      case 'storagePaths':
        return this.storagePaths
      default:
        return []
    }
  }

  getCustomFieldQueryModel(control: AbstractControl): CustomFieldQueriesModel {
    return this.ensureCustomFieldQueryModel(control as FormGroup)
  }

  onCustomFieldQuerySelectionChange(
    control: AbstractControl,
    model: CustomFieldQueriesModel
  ) {
    this.onCustomFieldQueryModelChanged(control as FormGroup, model)
  }

  isCustomFieldQueryValid(control: AbstractControl): boolean {
    const model = this.getStoredCustomFieldQueryModel(control as FormGroup)
    if (!model) {
      return true
    }

    return model.isEmpty() || model.isValid()
  }

  private getFilterTypeOptionsForArray(
    filters: FormArray
  ): TriggerFilterOption[] {
    let cached = this.triggerFilterOptionsMap.get(filters)
    if (!cached) {
      cached = this.filterDefinitions.map((definition) => ({
        ...definition,
        disabled: false,
      }))
      this.triggerFilterOptionsMap.set(filters, cached)
    }
    return cached
  }

  private ensureCustomFieldQueryModel(
    filterGroup: FormGroup,
    initialValue?: any
  ): CustomFieldQueriesModel {
    const existingModel = this.getStoredCustomFieldQueryModel(filterGroup)
    if (existingModel) {
      return existingModel
    }

    const model = new CustomFieldQueriesModel()
    this.setCustomFieldQueryModel(filterGroup, model)

    const rawValue =
      typeof initialValue === 'string'
        ? initialValue
        : (filterGroup.get('values').value as string)

    if (rawValue) {
      try {
        const parsed = JSON.parse(rawValue)
        const expression = new CustomFieldQueryExpression(parsed)
        model.queries = [expression]
      } catch {
        model.clear(false)
        model.addInitialAtom()
      }
    }

    const subscription = model.changed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.onCustomFieldQueryModelChanged(filterGroup, model)
      })
    filterGroup[CUSTOM_FIELD_QUERY_SUBSCRIPTION_KEY]?.unsubscribe()
    filterGroup[CUSTOM_FIELD_QUERY_SUBSCRIPTION_KEY] = subscription

    this.onCustomFieldQueryModelChanged(filterGroup, model)

    return model
  }

  private clearCustomFieldQueryModel(filterGroup: FormGroup) {
    const group = filterGroup as CustomFieldFilterGroup
    group[CUSTOM_FIELD_QUERY_SUBSCRIPTION_KEY]?.unsubscribe()
    delete group[CUSTOM_FIELD_QUERY_SUBSCRIPTION_KEY]
    delete group[CUSTOM_FIELD_QUERY_MODEL_KEY]
  }

  private getStoredCustomFieldQueryModel(
    filterGroup: FormGroup
  ): CustomFieldQueriesModel | null {
    return (
      (filterGroup as CustomFieldFilterGroup)[CUSTOM_FIELD_QUERY_MODEL_KEY] ??
      null
    )
  }

  private setCustomFieldQueryModel(
    filterGroup: FormGroup,
    model: CustomFieldQueriesModel
  ) {
    const group = filterGroup as CustomFieldFilterGroup
    group[CUSTOM_FIELD_QUERY_MODEL_KEY] = model
  }

  private onCustomFieldQueryModelChanged(
    filterGroup: FormGroup,
    model: CustomFieldQueriesModel
  ) {
    const control = filterGroup.get('values')
    if (!control) {
      return
    }

    if (!model.isValid()) {
      control.setValue(null, { emitEvent: false })
      return
    }

    if (model.isEmpty()) {
      control.setValue(null, { emitEvent: false })
      return
    }

    const serialized = JSON.stringify(model.queries[0].serialize())
    control.setValue(serialized, { emitEvent: false })
  }

  private getDefaultFilterValue(type: TriggerFilterType) {
    if (type === TriggerFilterType.CustomFieldQuery) {
      return null
    }
    return this.isMultiValueFilter(type) ? [] : null
  }

  private normalizeFilterValue(type: TriggerFilterType, value?: any) {
    if (value === undefined || value === null) {
      return this.getDefaultFilterValue(type)
    }

    if (type === TriggerFilterType.CustomFieldQuery) {
      if (typeof value === 'string') {
        return value
      }
      return value ? JSON.stringify(value) : null
    }

    if (this.isMultiValueFilter(type)) {
      return Array.isArray(value) ? [...value] : [value]
    }

    if (Array.isArray(value)) {
      return value.length > 0 ? value[0] : null
    }

    return value
  }

  private createTriggerField(
    trigger: WorkflowTrigger,
    emitEvent: boolean = false
  ) {
    this.triggerFields.push(
      new FormGroup({
        id: new FormControl(trigger.id),
        type: new FormControl(trigger.type),
        sources: new FormControl(trigger.sources),
        filter_filename: new FormControl(trigger.filter_filename),
        filter_path: new FormControl(trigger.filter_path),
        filter_mailrule: new FormControl(trigger.filter_mailrule),
        matching_algorithm: new FormControl(trigger.matching_algorithm),
        match: new FormControl(trigger.match),
        is_insensitive: new FormControl(trigger.is_insensitive),
        filters: this.buildFiltersFormArray(trigger),
        schedule_offset_days: new FormControl(trigger.schedule_offset_days),
        schedule_is_recurring: new FormControl(trigger.schedule_is_recurring),
        schedule_recurring_interval_days: new FormControl(
          trigger.schedule_recurring_interval_days
        ),
        schedule_date_field: new FormControl(trigger.schedule_date_field),
        schedule_date_custom_field: new FormControl(
          trigger.schedule_date_custom_field
        ),
      }),
      { emitEvent }
    )
  }

  private createActionField(
    action: WorkflowAction,
    emitEvent: boolean = false
  ) {
    this.actionFields.push(
      new FormGroup({
        id: new FormControl(action.id),
        type: new FormControl(action.type),
        assign_title: new FormControl(action.assign_title),
        assign_tags: new FormControl(action.assign_tags),
        assign_owner: new FormControl(action.assign_owner),
        assign_document_type: new FormControl(action.assign_document_type),
        assign_correspondent: new FormControl(action.assign_correspondent),
        assign_storage_path: new FormControl(action.assign_storage_path),
        assign_view_users: new FormControl(action.assign_view_users),
        assign_view_groups: new FormControl(action.assign_view_groups),
        assign_change_users: new FormControl(action.assign_change_users),
        assign_change_groups: new FormControl(action.assign_change_groups),
        assign_custom_fields: new FormControl(action.assign_custom_fields),
        assign_custom_fields_values: new FormControl(
          action.assign_custom_fields_values
        ),
        remove_tags: new FormControl(action.remove_tags),
        remove_all_tags: new FormControl(action.remove_all_tags),
        remove_document_types: new FormControl(action.remove_document_types),
        remove_all_document_types: new FormControl(
          action.remove_all_document_types
        ),
        remove_correspondents: new FormControl(action.remove_correspondents),
        remove_all_correspondents: new FormControl(
          action.remove_all_correspondents
        ),
        remove_storage_paths: new FormControl(action.remove_storage_paths),
        remove_all_storage_paths: new FormControl(
          action.remove_all_storage_paths
        ),
        remove_owners: new FormControl(action.remove_owners),
        remove_all_owners: new FormControl(action.remove_all_owners),
        remove_view_users: new FormControl(action.remove_view_users),
        remove_view_groups: new FormControl(action.remove_view_groups),
        remove_change_users: new FormControl(action.remove_change_users),
        remove_change_groups: new FormControl(action.remove_change_groups),
        remove_all_permissions: new FormControl(action.remove_all_permissions),
        remove_custom_fields: new FormControl(action.remove_custom_fields),
        remove_all_custom_fields: new FormControl(
          action.remove_all_custom_fields
        ),
        email: new FormGroup({
          id: new FormControl(action.email?.id),
          subject: new FormControl(action.email?.subject),
          body: new FormControl(action.email?.body),
          to: new FormControl(action.email?.to),
          include_document: new FormControl(!!action.email?.include_document),
        }),
        webhook: new FormGroup({
          id: new FormControl(action.webhook?.id),
          url: new FormControl(action.webhook?.url),
          use_params: new FormControl(action.webhook?.use_params),
          as_json: new FormControl(action.webhook?.as_json),
          params: new FormControl(action.webhook?.params),
          body: new FormControl(action.webhook?.body),
          headers: new FormControl(action.webhook?.headers),
          include_document: new FormControl(!!action.webhook?.include_document),
        }),
        passwords: new FormControl(
          this.formatPasswords(action.passwords ?? [])
        ),
      }),
      { emitEvent }
    )
  }

  private formatPasswords(passwords: string[] = []): string {
    return passwords.join('\n')
  }

  private parsePasswords(value: string = ''): string[] {
    return value
      .split(/[\n,]+/)
      .map((entry) => entry.trim())
      .filter((entry) => entry.length > 0)
  }

  private updateAllTriggerActionFields(emitEvent: boolean = false) {
    this.triggerFields.clear({ emitEvent: false })
    this.object?.triggers.forEach((trigger) => {
      this.createTriggerField(trigger, emitEvent)
    })

    this.actionFields.clear({ emitEvent: false })
    this.object?.actions.forEach((action) => {
      this.createActionField(action, emitEvent)
    })
  }

  get sourceOptions() {
    return DOCUMENT_SOURCE_OPTIONS
  }

  get triggerTypeOptions() {
    return WORKFLOW_TYPE_OPTIONS
  }

  get scheduleDateFieldOptions() {
    return SCHEDULE_DATE_FIELD_OPTIONS
  }

  getTriggerTypeOptionName(type: WorkflowTriggerType): string {
    return this.triggerTypeOptions.find((t) => t.id === type)?.name ?? ''
  }

  addTrigger() {
    if (!this.object) {
      this.object = Object.assign({}, this.objectForm.value)
    }
    const trigger: WorkflowTrigger = {
      type: WorkflowTriggerType.Consumption,
      sources: [],
      filter_filename: null,
      filter_path: null,
      filter_mailrule: null,
      filter_has_tags: [],
      filter_has_all_tags: [],
      filter_has_not_tags: [],
      filter_has_any_correspondents: [],
      filter_has_not_correspondents: [],
      filter_has_any_document_types: [],
      filter_has_not_document_types: [],
      filter_has_any_storage_paths: [],
      filter_has_not_storage_paths: [],
      filter_custom_field_query: null,
      filter_has_correspondent: null,
      filter_has_document_type: null,
      filter_has_storage_path: null,
      matching_algorithm: MATCH_NONE,
      match: '',
      is_insensitive: true,
      schedule_offset_days: 0,
      schedule_is_recurring: false,
      schedule_recurring_interval_days: 1,
      schedule_date_field: ScheduleDateField.Added,
      schedule_date_custom_field: null,
    }
    this.object.triggers.push(trigger)
    this.createTriggerField(trigger)
  }

  get actionTypeOptions() {
    return this.allowedActionTypes
  }

  getActionTypeOptionName(type: WorkflowActionType): string {
    return this.actionTypeOptions.find((t) => t.id === type)?.name ?? ''
  }

  addAction() {
    if (!this.object) {
      this.object = Object.assign({}, this.objectForm.value)
    }
    const action: WorkflowAction = {
      type: WorkflowActionType.Assignment,
      assign_title: null,
      assign_tags: [],
      assign_document_type: null,
      assign_correspondent: null,
      assign_storage_path: null,
      assign_owner: null,
      assign_view_users: [],
      assign_view_groups: [],
      assign_change_users: [],
      assign_change_groups: [],
      assign_custom_fields: [],
      assign_custom_fields_values: {},
      remove_tags: [],
      remove_all_tags: false,
      remove_document_types: [],
      remove_all_document_types: false,
      remove_correspondents: [],
      remove_all_correspondents: false,
      remove_storage_paths: [],
      remove_all_storage_paths: false,
      remove_owners: [],
      remove_all_owners: false,
      remove_view_users: [],
      remove_view_groups: [],
      remove_change_users: [],
      remove_change_groups: [],
      remove_all_permissions: false,
      remove_custom_fields: [],
      remove_all_custom_fields: false,
      email: {
        id: null,
        subject: null,
        body: null,
        to: null,
        include_document: false,
      },
      webhook: {
        id: null,
        url: null,
        use_params: true,
        as_json: false,
        params: null,
        body: null,
        headers: null,
        include_document: false,
      },
      passwords: [],
    }
    this.object.actions.push(action)
    this.createActionField(action)
  }

  removeTrigger(index: number) {
    this.object.triggers.splice(index, 1).pop()
    this.triggerFields.removeAt(index)
  }

  removeAction(index: number) {
    this.object.actions.splice(index, 1)
    this.actionFields.removeAt(index)
  }

  onActionDrop(event: CdkDragDrop<WorkflowAction[]>) {
    moveItemInArray(
      this.object.actions,
      event.previousIndex,
      event.currentIndex
    )
    const actionField = this.actionFields.at(event.previousIndex)
    this.actionFields.removeAt(event.previousIndex)
    this.actionFields.insert(event.currentIndex, actionField)
  }

  save(): void {
    this.objectForm
      .get('actions')
      .value.forEach((action: WorkflowAction, i) => {
        if (action.type !== WorkflowActionType.Webhook) {
          action.webhook = null
        }
        if (action.type !== WorkflowActionType.Email) {
          action.email = null
        }
        action.passwords = this.parsePasswords(action.passwords as any)
      })
    super.save()
  }

  public removeSelectedCustomField(fieldId: number, group: FormGroup) {
    group
      .get('assign_custom_fields')
      .setValue(
        group.get('assign_custom_fields').value.filter((id) => id !== fieldId)
      )
  }
}
