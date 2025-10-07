import { CdkDragDrop } from '@angular/cdk/drag-drop'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { of } from 'rxjs'
import { CustomFieldQueriesModel } from 'src/app/components/common/custom-fields-query-dropdown/custom-fields-query-dropdown.component'
import { CustomFieldDataType } from 'src/app/data/custom-field'
import { CustomFieldQueryLogicalOperator } from 'src/app/data/custom-field-query'
import {
  MATCHING_ALGORITHMS,
  MATCH_AUTO,
  MATCH_NONE,
} from 'src/app/data/matching-model'
import { Workflow } from 'src/app/data/workflow'
import {
  WorkflowAction,
  WorkflowActionType,
} from 'src/app/data/workflow-action'
import {
  DocumentSource,
  WorkflowTriggerType,
} from 'src/app/data/workflow-trigger'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CustomFieldQueryExpression } from 'src/app/utils/custom-field-query-element'
import { ConfirmButtonComponent } from '../../confirm-button/confirm-button.component'
import { NumberComponent } from '../../input/number/number.component'
import { PermissionsGroupComponent } from '../../input/permissions/permissions-group/permissions-group.component'
import { PermissionsUserComponent } from '../../input/permissions/permissions-user/permissions-user.component'
import { SelectComponent } from '../../input/select/select.component'
import { SwitchComponent } from '../../input/switch/switch.component'
import { TagsComponent } from '../../input/tags/tags.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogMode } from '../edit-dialog.component'
import {
  DOCUMENT_SOURCE_OPTIONS,
  SCHEDULE_DATE_FIELD_OPTIONS,
  TriggerConditionType,
  WORKFLOW_ACTION_OPTIONS,
  WORKFLOW_TYPE_OPTIONS,
  WorkflowEditDialogComponent,
} from './workflow-edit-dialog.component'

const workflow: Workflow = {
  name: 'Workflow 1',
  id: 1,
  order: 1,
  enabled: true,
  triggers: [
    {
      id: 1,
      type: WorkflowTriggerType.Consumption,
      sources: [DocumentSource.ConsumeFolder],
      filter_filename: '*',
    },
  ],
  actions: [
    {
      id: 1,
      type: WorkflowActionType.Assignment,
      assign_title: 'foo',
    },
    {
      id: 4,
      type: WorkflowActionType.Assignment,
      assign_owner: 2,
    },
  ],
}

describe('WorkflowEditDialogComponent', () => {
  let component: WorkflowEditDialogComponent
  let settingsService: SettingsService
  let fixture: ComponentFixture<WorkflowEditDialogComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
        WorkflowEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        NumberComponent,
        SwitchComponent,
        TagsComponent,
        PermissionsUserComponent,
        PermissionsGroupComponent,
        SafeHtmlPipe,
        ConfirmButtonComponent,
      ],
      providers: [
        NgbActiveModal,
        {
          provide: CorrespondentService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 1,
                    username: 'c1',
                  },
                ],
              }),
          },
        },
        {
          provide: DocumentTypeService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 1,
                    username: 'dt1',
                  },
                ],
              }),
          },
        },
        {
          provide: StoragePathService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 1,
                    username: 'sp1',
                  },
                ],
              }),
          },
        },
        {
          provide: MailRuleService,
          useValue: {
            listAll: () =>
              of({
                results: [],
              }),
          },
        },
        {
          provide: CustomFieldsService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 1,
                    name: 'cf1',
                    data_type: CustomFieldDataType.String,
                  },
                  {
                    id: 2,
                    name: 'cf2',
                    data_type: CustomFieldDataType.Date,
                  },
                ],
              }),
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(WorkflowEditDialogComponent)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = { id: 99, username: 'user99' }
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support create and edit modes, support adding triggers and actions on new workflow', () => {
    component.dialogMode = EditDialogMode.CREATE
    const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
    const editTitleSpy = jest.spyOn(component, 'getEditTitle')
    fixture.detectChanges()
    expect(createTitleSpy).toHaveBeenCalled()
    expect(editTitleSpy).not.toHaveBeenCalled()
    expect(component.object).toBeUndefined()
    component.addAction()
    expect(component.object).not.toBeUndefined()
    expect(component.object.actions).toHaveLength(1)
    component.object = undefined
    component.addTrigger()
    expect(component.object).not.toBeUndefined()
    expect(component.object.triggers).toHaveLength(1)

    component.dialogMode = EditDialogMode.EDIT
    fixture.detectChanges()
    expect(editTitleSpy).toHaveBeenCalled()
  })

  it('should return source options, type options, type name, schedule date field options', () => {
    jest.spyOn(settingsService, 'get').mockReturnValue(true)
    component.ngOnInit()
    expect(component.sourceOptions).toEqual(DOCUMENT_SOURCE_OPTIONS)
    expect(component.triggerTypeOptions).toEqual(WORKFLOW_TYPE_OPTIONS)
    expect(
      component.getTriggerTypeOptionName(WorkflowTriggerType.DocumentAdded)
    ).toEqual('Document Added')
    expect(component.getTriggerTypeOptionName(null)).toEqual('')
    expect(component.sourceOptions).toEqual(DOCUMENT_SOURCE_OPTIONS)
    expect(component.actionTypeOptions).toEqual(WORKFLOW_ACTION_OPTIONS)
    expect(
      component.getActionTypeOptionName(WorkflowActionType.Assignment)
    ).toEqual('Assignment')
    expect(component.getActionTypeOptionName(null)).toEqual('')
    expect(component.scheduleDateFieldOptions).toEqual(
      SCHEDULE_DATE_FIELD_OPTIONS
    )

    // Email disabled
    jest.spyOn(settingsService, 'get').mockReturnValue(false)
    component.ngOnInit()
    expect(component.actionTypeOptions).toEqual(
      WORKFLOW_ACTION_OPTIONS.filter((a) => a.id !== WorkflowActionType.Email)
    )
  })

  it('should support add and remove triggers and actions', () => {
    component.object = workflow
    component.addTrigger()
    expect(component.object.triggers.length).toEqual(2)
    component.addAction()
    expect(component.object.actions.length).toEqual(3)
    component.removeTrigger(1)
    expect(component.object.triggers.length).toEqual(1)
    component.removeAction(1)
    expect(component.object.actions.length).toEqual(2)
  })

  it('should update order and remove ids from actions on drag n drop', () => {
    const action1 = workflow.actions[0]
    const action2 = workflow.actions[1]
    component.object = workflow
    component.ngOnInit()
    component.onActionDrop({ previousIndex: 0, currentIndex: 1 } as CdkDragDrop<
      WorkflowAction[]
    >)
    expect(component.object.actions).toEqual([action2, action1])
    expect(action1.id).toBeNull()
    expect(action2.id).toBeNull()
  })

  it('should not include auto matching in algorithms', () => {
    expect(component.getMatchingAlgorithms()).not.toContain(
      MATCHING_ALGORITHMS.find((a) => a.id === MATCH_AUTO)
    )
  })

  it('should disable or enable action fields based on removal action type', () => {
    const workflow: Workflow = {
      name: 'Workflow 1',
      id: 1,
      order: 1,
      enabled: true,
      triggers: [],
      actions: [
        {
          id: 1,
          type: WorkflowActionType.Removal,
          remove_all_tags: true,
          remove_all_document_types: true,
          remove_all_correspondents: true,
          remove_all_storage_paths: true,
          remove_all_custom_fields: true,
          remove_all_owners: true,
          remove_all_permissions: true,
        },
      ],
    }
    component.object = workflow
    component.ngOnInit()

    component['checkRemovalActionFields'](workflow)

    // Assert that the action fields are disabled or enabled correctly
    expect(
      component.actionFields.at(0).get('remove_tags').disabled
    ).toBeTruthy()
    expect(
      component.actionFields.at(0).get('remove_document_types').disabled
    ).toBeTruthy()
    expect(
      component.actionFields.at(0).get('remove_correspondents').disabled
    ).toBeTruthy()
    expect(
      component.actionFields.at(0).get('remove_storage_paths').disabled
    ).toBeTruthy()
    expect(
      component.actionFields.at(0).get('remove_custom_fields').disabled
    ).toBeTruthy()
    expect(
      component.actionFields.at(0).get('remove_owners').disabled
    ).toBeTruthy()
    expect(
      component.actionFields.at(0).get('remove_view_users').disabled
    ).toBeTruthy()
    expect(
      component.actionFields.at(0).get('remove_view_groups').disabled
    ).toBeTruthy()
    expect(
      component.actionFields.at(0).get('remove_change_users').disabled
    ).toBeTruthy()
    expect(
      component.actionFields.at(0).get('remove_change_groups').disabled
    ).toBeTruthy()

    workflow.actions[0].remove_all_tags = false
    workflow.actions[0].remove_all_document_types = false
    workflow.actions[0].remove_all_correspondents = false
    workflow.actions[0].remove_all_storage_paths = false
    workflow.actions[0].remove_all_custom_fields = false
    workflow.actions[0].remove_all_owners = false
    workflow.actions[0].remove_all_permissions = false

    component['checkRemovalActionFields'](workflow)

    // Assert that the action fields are disabled or enabled correctly
    expect(component.actionFields.at(0).get('remove_tags').disabled).toBeFalsy()
    expect(
      component.actionFields.at(0).get('remove_document_types').disabled
    ).toBeFalsy()
    expect(
      component.actionFields.at(0).get('remove_correspondents').disabled
    ).toBeFalsy()
    expect(
      component.actionFields.at(0).get('remove_storage_paths').disabled
    ).toBeFalsy()
    expect(
      component.actionFields.at(0).get('remove_custom_fields').disabled
    ).toBeFalsy()
    expect(
      component.actionFields.at(0).get('remove_owners').disabled
    ).toBeFalsy()
    expect(
      component.actionFields.at(0).get('remove_view_users').disabled
    ).toBeFalsy()
    expect(
      component.actionFields.at(0).get('remove_view_groups').disabled
    ).toBeFalsy()
    expect(
      component.actionFields.at(0).get('remove_change_users').disabled
    ).toBeFalsy()
    expect(
      component.actionFields.at(0).get('remove_change_groups').disabled
    ).toBeFalsy()
  })

  it('should prune empty nested objects on save', () => {
    component.object = workflow
    component.addTrigger()
    component.addAction()
    expect(component.objectForm.get('actions').value[0].email).not.toBeNull()
    expect(component.objectForm.get('actions').value[0].webhook).not.toBeNull()
    component.save()
    expect(component.objectForm.get('actions').value[0].email).toBeNull()
    expect(component.objectForm.get('actions').value[0].webhook).toBeNull()
  })

  it('should require matching pattern when algorithm is not none', () => {
    const triggerGroup = new FormGroup({
      matching_algorithm: new FormControl(MATCH_AUTO),
      match: new FormControl(''),
    })
    expect(component.matchingPatternRequired(triggerGroup)).toBe(true)
    triggerGroup.get('matching_algorithm').setValue(MATCHING_ALGORITHMS[0].id)
    expect(component.matchingPatternRequired(triggerGroup)).toBe(true)
    triggerGroup.get('matching_algorithm').setValue(MATCH_NONE)
    expect(component.matchingPatternRequired(triggerGroup)).toBe(false)
  })

  it('should map condition builder values into trigger filters on save', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0)
    component.addCondition(triggerGroup as FormGroup)
    component.addCondition(triggerGroup as FormGroup)
    component.addCondition(triggerGroup as FormGroup)

    const conditions = component.getConditionsFormArray(
      triggerGroup as FormGroup
    )
    expect(conditions.length).toBe(3)

    conditions.at(0).get('values').setValue([1])
    conditions.at(1).get('values').setValue([2, 3])
    conditions.at(2).get('values').setValue([4])

    const addConditionOfType = (type: TriggerConditionType) => {
      const newCondition = component.addCondition(triggerGroup as FormGroup)
      newCondition.get('type').setValue(type)
      return newCondition
    }

    const correspondentIs = addConditionOfType(
      TriggerConditionType.CorrespondentIs
    )
    correspondentIs.get('values').setValue(1)

    const correspondentNot = addConditionOfType(
      TriggerConditionType.CorrespondentNot
    )
    correspondentNot.get('values').setValue([1])

    const documentTypeIs = addConditionOfType(
      TriggerConditionType.DocumentTypeIs
    )
    documentTypeIs.get('values').setValue(1)

    const documentTypeNot = addConditionOfType(
      TriggerConditionType.DocumentTypeNot
    )
    documentTypeNot.get('values').setValue([1])

    const storagePathIs = addConditionOfType(TriggerConditionType.StoragePathIs)
    storagePathIs.get('values').setValue(1)

    const storagePathNot = addConditionOfType(
      TriggerConditionType.StoragePathNot
    )
    storagePathNot.get('values').setValue([1])

    const customFieldCondition = addConditionOfType(
      TriggerConditionType.CustomFieldQuery
    )
    const customFieldQuery = JSON.stringify(['AND', [[1, 'exact', 'test']]])
    customFieldCondition.get('values').setValue(customFieldQuery)

    const formValues = component['getFormValues']()

    expect(formValues.triggers[0].filter_has_tags).toEqual([1])
    expect(formValues.triggers[0].filter_has_all_tags).toEqual([2, 3])
    expect(formValues.triggers[0].filter_has_not_tags).toEqual([4])
    expect(formValues.triggers[0].filter_has_correspondent).toEqual(1)
    expect(formValues.triggers[0].filter_has_not_correspondents).toEqual([1])
    expect(formValues.triggers[0].filter_has_document_type).toEqual(1)
    expect(formValues.triggers[0].filter_has_not_document_types).toEqual([1])
    expect(formValues.triggers[0].filter_has_storage_path).toEqual(1)
    expect(formValues.triggers[0].filter_has_not_storage_paths).toEqual([1])
    expect(formValues.triggers[0].filter_custom_field_query).toEqual(
      customFieldQuery
    )
    expect(formValues.triggers[0].conditions).toBeUndefined()
  })

  it('should ignore empty and null condition values when mapping filters', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    const tagsCondition = component.addCondition(triggerGroup)
    tagsCondition.get('type').setValue(TriggerConditionType.TagsAny)
    tagsCondition.get('values').setValue([])

    const correspondentCondition = component.addCondition(triggerGroup)
    correspondentCondition
      .get('type')
      .setValue(TriggerConditionType.CorrespondentIs)
    correspondentCondition.get('values').setValue(null)

    const formValues = component['getFormValues']()

    expect(formValues.triggers[0].filter_has_tags).toEqual([])
    expect(formValues.triggers[0].filter_has_correspondent).toBeNull()
  })

  it('should derive single select filters from array values', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    const addConditionOfType = (type: TriggerConditionType, value: any) => {
      const condition = component.addCondition(triggerGroup)
      condition.get('type').setValue(type)
      condition.get('values').setValue(value)
    }

    addConditionOfType(TriggerConditionType.CorrespondentIs, [5])
    addConditionOfType(TriggerConditionType.DocumentTypeIs, [6])
    addConditionOfType(TriggerConditionType.StoragePathIs, [7])

    const formValues = component['getFormValues']()

    expect(formValues.triggers[0].filter_has_correspondent).toEqual(5)
    expect(formValues.triggers[0].filter_has_document_type).toEqual(6)
    expect(formValues.triggers[0].filter_has_storage_path).toEqual(7)
  })

  it('should reuse cached condition type options and update disabled state', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup
    component.addCondition(triggerGroup)

    const optionsFirst = component.getConditionTypeOptions(triggerGroup, 0)
    const optionsSecond = component.getConditionTypeOptions(triggerGroup, 0)
    expect(optionsFirst).toBe(optionsSecond)

    // to force disabled flag
    component.addCondition(triggerGroup)
    const conditionArray = component.getConditionsFormArray(triggerGroup)
    const firstCondition = conditionArray.at(0)
    firstCondition.get('type').setValue(TriggerConditionType.CorrespondentIs)

    component.addCondition(triggerGroup)
    const updatedConditions = component.getConditionsFormArray(triggerGroup)
    const secondCondition = updatedConditions.at(1)
    const options = component.getConditionTypeOptions(triggerGroup, 1)
    const correspondentIsOption = options.find(
      (option) => option.id === TriggerConditionType.CorrespondentIs
    )
    expect(correspondentIsOption.disabled).toBe(true)

    firstCondition.get('type').setValue(TriggerConditionType.DocumentTypeNot)
    secondCondition.get('type').setValue(TriggerConditionType.TagsAll)
    const postChangeOptions = component.getConditionTypeOptions(triggerGroup, 1)
    const correspondentOptionAfter = postChangeOptions.find(
      (option) => option.id === TriggerConditionType.CorrespondentIs
    )
    expect(correspondentOptionAfter.disabled).toBe(false)
  })

  it('should keep multi-entry condition options enabled and allow duplicates', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    component.conditionDefinitions = [
      {
        id: TriggerConditionType.TagsAny,
        name: 'Any tags',
        inputType: 'tags',
        allowMultipleEntries: true,
        allowMultipleValues: true,
      } as any,
      {
        id: TriggerConditionType.CorrespondentIs,
        name: 'Correspondent is',
        inputType: 'select',
        allowMultipleEntries: false,
        allowMultipleValues: false,
        selectItems: 'correspondents',
      } as any,
    ]

    const firstCondition = component.addCondition(triggerGroup)
    firstCondition.get('type').setValue(TriggerConditionType.TagsAny)

    const secondCondition = component.addCondition(triggerGroup)
    expect(secondCondition).not.toBeNull()

    const options = component.getConditionTypeOptions(triggerGroup, 1)
    const multiEntryOption = options.find(
      (option) => option.id === TriggerConditionType.TagsAny
    )

    expect(multiEntryOption.disabled).toBe(false)
    expect(component.canAddCondition(triggerGroup)).toBe(true)
  })

  it('should return null when no condition definitions remain available', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    component.conditionDefinitions = [
      {
        id: TriggerConditionType.TagsAny,
        name: 'Any tags',
        inputType: 'tags',
        allowMultipleEntries: false,
        allowMultipleValues: true,
      } as any,
      {
        id: TriggerConditionType.CorrespondentIs,
        name: 'Correspondent is',
        inputType: 'select',
        allowMultipleEntries: false,
        allowMultipleValues: false,
        selectItems: 'correspondents',
      } as any,
    ]

    const firstCondition = component.addCondition(triggerGroup)
    firstCondition.get('type').setValue(TriggerConditionType.TagsAny)
    const secondCondition = component.addCondition(triggerGroup)
    secondCondition.get('type').setValue(TriggerConditionType.CorrespondentIs)

    expect(component.canAddCondition(triggerGroup)).toBe(false)
    expect(component.addCondition(triggerGroup)).toBeNull()
  })

  it('should return null when adding condition for unknown trigger form group', () => {
    expect(component.addCondition(new FormGroup({}) as any)).toBeNull()
  })

  it('should ignore remove condition calls for unknown trigger form group', () => {
    expect(() =>
      component.removeCondition(new FormGroup({}) as any, 0)
    ).not.toThrow()
  })

  it('should teardown custom field query model when removing a custom field condition', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    component.addCondition(triggerGroup)
    const conditions = component.getConditionsFormArray(triggerGroup)
    const conditionGroup = conditions.at(0) as FormGroup
    conditionGroup.get('type').setValue(TriggerConditionType.CustomFieldQuery)

    const model = component.getCustomFieldQueryModel(conditionGroup)
    expect(model).toBeDefined()
    expect(component['customFieldQueryModels'].has(conditionGroup)).toBe(true)

    component.removeCondition(triggerGroup, 0)
    expect(component['customFieldQueryModels'].has(conditionGroup)).toBe(false)
  })

  it('should return readable condition names', () => {
    expect(component.getConditionName(TriggerConditionType.TagsAny)).toBe(
      'Has any of these tags'
    )
    expect(component.getConditionName(999 as any)).toBe('')
  })

  it('should build condition form array from existing trigger filters', () => {
    const trigger = workflow.triggers[0]
    trigger.filter_has_tags = [1]
    trigger.filter_has_all_tags = [2, 3]
    trigger.filter_has_not_tags = [4]
    trigger.filter_has_correspondent = 5 as any
    trigger.filter_has_not_correspondents = [6] as any
    trigger.filter_has_document_type = 7 as any
    trigger.filter_has_not_document_types = [8] as any
    trigger.filter_has_storage_path = 9 as any
    trigger.filter_has_not_storage_paths = [10] as any
    trigger.filter_custom_field_query = JSON.stringify([
      'AND',
      [[1, 'exact', 'value']],
    ]) as any

    component.object = workflow
    component.ngOnInit()
    const triggerGroup = component.triggerFields.at(0) as FormGroup
    const conditions = component.getConditionsFormArray(triggerGroup)
    expect(conditions.length).toBe(10)
    const customFieldCondition = conditions.at(9) as FormGroup
    expect(customFieldCondition.get('type').value).toBe(
      TriggerConditionType.CustomFieldQuery
    )
    const model = component.getCustomFieldQueryModel(customFieldCondition)
    expect(model.isValid()).toBe(true)
  })

  it('should expose select metadata helpers', () => {
    expect(
      component.isSelectMultiple(TriggerConditionType.CorrespondentNot)
    ).toBe(true)
    expect(
      component.isSelectMultiple(TriggerConditionType.CorrespondentIs)
    ).toBe(false)

    component.correspondents = [{ id: 1, name: 'C1' } as any]
    component.documentTypes = [{ id: 2, name: 'DT' } as any]
    component.storagePaths = [{ id: 3, name: 'SP' } as any]

    expect(
      component.getConditionSelectItems(TriggerConditionType.CorrespondentIs)
    ).toEqual(component.correspondents)
    expect(
      component.getConditionSelectItems(TriggerConditionType.DocumentTypeIs)
    ).toEqual(component.documentTypes)
    expect(
      component.getConditionSelectItems(TriggerConditionType.StoragePathIs)
    ).toEqual(component.storagePaths)
    expect(
      component.getConditionSelectItems(TriggerConditionType.TagsAll)
    ).toEqual([])

    expect(
      component.isCustomFieldQueryCondition(
        TriggerConditionType.CustomFieldQuery
      )
    ).toBe(true)
  })

  it('should handle custom field query selection change and validation states', () => {
    const formGroup = new FormGroup({
      values: new FormControl(null),
    })
    const model = new CustomFieldQueriesModel()

    const changeSpy = jest.spyOn(
      component as any,
      'onCustomFieldQueryModelChanged'
    )

    component.onCustomFieldQuerySelectionChange(formGroup, model)
    expect(changeSpy).toHaveBeenCalledWith(formGroup, model)

    const map = component['customFieldQueryModels']

    expect(component.isCustomFieldQueryValid(formGroup)).toBe(true)
    map.set(formGroup, model)

    const validSpy = jest.spyOn(model, 'isValid').mockReturnValue(false)
    const emptySpy = jest.spyOn(model, 'isEmpty').mockReturnValue(false)
    expect(component.isCustomFieldQueryValid(formGroup)).toBe(false)
    expect(validSpy).toHaveBeenCalled()

    validSpy.mockReturnValue(true)
    emptySpy.mockReturnValue(true)
    expect(component.isCustomFieldQueryValid(formGroup)).toBe(true)

    emptySpy.mockReturnValue(false)
    expect(component.isCustomFieldQueryValid(formGroup)).toBe(true)

    map.delete(formGroup)
  })

  it('should recover from invalid custom field query json and update control on changes', () => {
    const conditionGroup = new FormGroup({
      values: new FormControl('not-json'),
    })

    component['ensureCustomFieldQueryModel'](conditionGroup, 'not-json')

    const model = component['customFieldQueryModels'].get(conditionGroup)
    expect(model).toBeDefined()
    expect(model.queries.length).toBeGreaterThan(0)

    const valuesControl = conditionGroup.get('values')
    expect(valuesControl.value).toBeNull()

    const expression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.And,
      [[1, 'exact', 'value']],
    ])
    model.queries = [expression]

    jest.spyOn(model, 'isValid').mockReturnValue(true)
    jest.spyOn(model, 'isEmpty').mockReturnValue(false)

    model.changed.next(model)

    expect(valuesControl.value).toEqual(JSON.stringify(expression.serialize()))

    component['teardownCustomFieldQueryModel'](conditionGroup)
  })

  it('should handle custom field query model change edge cases', () => {
    const groupWithoutControl = new FormGroup({})
    const dummyModel = {
      isValid: jest.fn().mockReturnValue(true),
      isEmpty: jest.fn().mockReturnValue(false),
    }

    expect(() =>
      component['onCustomFieldQueryModelChanged'](
        groupWithoutControl as any,
        dummyModel as any
      )
    ).not.toThrow()

    const groupWithControl = new FormGroup({
      values: new FormControl('initial'),
    })
    const emptyModel = {
      isValid: jest.fn().mockReturnValue(true),
      isEmpty: jest.fn().mockReturnValue(true),
    }

    component['onCustomFieldQueryModelChanged'](
      groupWithControl as any,
      emptyModel as any
    )

    expect(groupWithControl.get('values').value).toBeNull()
  })

  it('should normalize condition values for single and multi selects', () => {
    expect(
      component['normalizeConditionValue'](TriggerConditionType.TagsAny)
    ).toEqual([])
    expect(
      component['normalizeConditionValue'](TriggerConditionType.TagsAny, 5)
    ).toEqual([5])
    expect(
      component['normalizeConditionValue'](TriggerConditionType.TagsAny, [5, 6])
    ).toEqual([5, 6])
    expect(
      component['normalizeConditionValue'](
        TriggerConditionType.CorrespondentIs,
        [7]
      )
    ).toEqual(7)
    expect(
      component['normalizeConditionValue'](
        TriggerConditionType.CorrespondentIs,
        8
      )
    ).toEqual(8)
    const customFieldJson = JSON.stringify(['AND', [[1, 'exact', 'test']]])
    expect(
      component['normalizeConditionValue'](
        TriggerConditionType.CustomFieldQuery,
        customFieldJson
      )
    ).toEqual(customFieldJson)
  })

  it('should add and remove condition form groups', () => {
    component['changeDetector'] = { detectChanges: jest.fn() } as any
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    component.addCondition(triggerGroup)

    component.removeCondition(triggerGroup, 0)
    expect(component.getConditionsFormArray(triggerGroup).length).toBe(0)

    component.addCondition(triggerGroup)
    const conditionArrayAfterAdd =
      component.getConditionsFormArray(triggerGroup)
    conditionArrayAfterAdd
      .at(0)
      .get('type')
      .setValue(TriggerConditionType.TagsAll)
    expect(component.getConditionsFormArray(triggerGroup).length).toBe(1)
  })

  it('should remove selected custom field from the form group', () => {
    const formGroup = new FormGroup({
      assign_custom_fields: new FormControl([1, 2, 3]),
    })

    component.removeSelectedCustomField(2, formGroup)
    expect(formGroup.get('assign_custom_fields').value).toEqual([1, 3])

    component.removeSelectedCustomField(1, formGroup)
    expect(formGroup.get('assign_custom_fields').value).toEqual([3])

    component.removeSelectedCustomField(3, formGroup)
    expect(formGroup.get('assign_custom_fields').value).toEqual([])
  })
})
