import { CdkDragDrop } from '@angular/cdk/drag-drop'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormArray,
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
  TriggerFilterType,
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

  it('should update order on drag n drop', () => {
    const action1 = workflow.actions[0]
    const action2 = workflow.actions[1]
    component.object = workflow
    component.ngOnInit()
    component.onActionDrop({ previousIndex: 0, currentIndex: 1 } as CdkDragDrop<
      WorkflowAction[]
    >)
    expect(component.object.actions).toEqual([action2, action1])
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

  it('should map filter builder values into trigger filters on save', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0)
    component.addFilter(triggerGroup as FormGroup)
    component.addFilter(triggerGroup as FormGroup)
    component.addFilter(triggerGroup as FormGroup)

    const filters = component.getFiltersFormArray(triggerGroup as FormGroup)
    expect(filters.length).toBe(3)

    filters.at(0).get('values').setValue([1])
    filters.at(1).get('values').setValue([2, 3])
    filters.at(2).get('values').setValue([4])

    const addFilterOfType = (type: TriggerFilterType) => {
      const newFilter = component.addFilter(triggerGroup as FormGroup)
      newFilter.get('type').setValue(type)
      return newFilter
    }

    const correspondentAny = addFilterOfType(TriggerFilterType.CorrespondentAny)
    correspondentAny.get('values').setValue([11])

    const correspondentIs = addFilterOfType(TriggerFilterType.CorrespondentIs)
    correspondentIs.get('values').setValue(1)

    const correspondentNot = addFilterOfType(TriggerFilterType.CorrespondentNot)
    correspondentNot.get('values').setValue([1])

    const documentTypeIs = addFilterOfType(TriggerFilterType.DocumentTypeIs)
    documentTypeIs.get('values').setValue(1)

    const documentTypeAny = addFilterOfType(TriggerFilterType.DocumentTypeAny)
    documentTypeAny.get('values').setValue([12])

    const documentTypeNot = addFilterOfType(TriggerFilterType.DocumentTypeNot)
    documentTypeNot.get('values').setValue([1])

    const storagePathIs = addFilterOfType(TriggerFilterType.StoragePathIs)
    storagePathIs.get('values').setValue(1)

    const storagePathAny = addFilterOfType(TriggerFilterType.StoragePathAny)
    storagePathAny.get('values').setValue([13])

    const storagePathNot = addFilterOfType(TriggerFilterType.StoragePathNot)
    storagePathNot.get('values').setValue([1])

    const customFieldFilter = addFilterOfType(
      TriggerFilterType.CustomFieldQuery
    )
    const customFieldQuery = JSON.stringify(['AND', [[1, 'exact', 'test']]])
    customFieldFilter.get('values').setValue(customFieldQuery)

    const formValues = component['getFormValues']()

    expect(formValues.triggers[0].filter_has_tags).toEqual([1])
    expect(formValues.triggers[0].filter_has_all_tags).toEqual([2, 3])
    expect(formValues.triggers[0].filter_has_not_tags).toEqual([4])
    expect(formValues.triggers[0].filter_has_any_correspondents).toEqual([11])
    expect(formValues.triggers[0].filter_has_correspondent).toEqual(1)
    expect(formValues.triggers[0].filter_has_not_correspondents).toEqual([1])
    expect(formValues.triggers[0].filter_has_any_document_types).toEqual([12])
    expect(formValues.triggers[0].filter_has_document_type).toEqual(1)
    expect(formValues.triggers[0].filter_has_not_document_types).toEqual([1])
    expect(formValues.triggers[0].filter_has_any_storage_paths).toEqual([13])
    expect(formValues.triggers[0].filter_has_storage_path).toEqual(1)
    expect(formValues.triggers[0].filter_has_not_storage_paths).toEqual([1])
    expect(formValues.triggers[0].filter_custom_field_query).toEqual(
      customFieldQuery
    )
    expect(formValues.triggers[0].filters).toBeUndefined()
  })

  it('should ignore empty and null filter values when mapping filters', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    const tagsFilter = component.addFilter(triggerGroup)
    tagsFilter.get('type').setValue(TriggerFilterType.TagsAny)
    tagsFilter.get('values').setValue([])

    const correspondentFilter = component.addFilter(triggerGroup)
    correspondentFilter.get('type').setValue(TriggerFilterType.CorrespondentIs)
    correspondentFilter.get('values').setValue(null)

    const formValues = component['getFormValues']()

    expect(formValues.triggers[0].filter_has_tags).toEqual([])
    expect(formValues.triggers[0].filter_has_correspondent).toBeNull()
  })

  it('should derive single select filters from array values', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    const addFilterOfType = (type: TriggerFilterType, value: any) => {
      const filter = component.addFilter(triggerGroup)
      filter.get('type').setValue(type)
      filter.get('values').setValue(value)
    }

    addFilterOfType(TriggerFilterType.CorrespondentIs, [5])
    addFilterOfType(TriggerFilterType.DocumentTypeIs, [6])
    addFilterOfType(TriggerFilterType.StoragePathIs, [7])

    const formValues = component['getFormValues']()

    expect(formValues.triggers[0].filter_has_correspondent).toEqual(5)
    expect(formValues.triggers[0].filter_has_document_type).toEqual(6)
    expect(formValues.triggers[0].filter_has_storage_path).toEqual(7)
  })

  it('should convert multi-value filter values when aggregating filters', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    const setFilter = (type: TriggerFilterType, value: number): void => {
      const filter = component.addFilter(triggerGroup) as FormGroup
      filter.get('type').setValue(type)
      filter.get('values').setValue(value)
    }

    setFilter(TriggerFilterType.TagsAll, 11)
    setFilter(TriggerFilterType.TagsNone, 12)
    setFilter(TriggerFilterType.CorrespondentAny, 16)
    setFilter(TriggerFilterType.CorrespondentNot, 13)
    setFilter(TriggerFilterType.DocumentTypeAny, 17)
    setFilter(TriggerFilterType.DocumentTypeNot, 14)
    setFilter(TriggerFilterType.StoragePathAny, 18)
    setFilter(TriggerFilterType.StoragePathNot, 15)

    const formValues = component['getFormValues']()

    expect(formValues.triggers[0].filter_has_all_tags).toEqual([11])
    expect(formValues.triggers[0].filter_has_not_tags).toEqual([12])
    expect(formValues.triggers[0].filter_has_any_correspondents).toEqual([16])
    expect(formValues.triggers[0].filter_has_not_correspondents).toEqual([13])
    expect(formValues.triggers[0].filter_has_any_document_types).toEqual([17])
    expect(formValues.triggers[0].filter_has_not_document_types).toEqual([14])
    expect(formValues.triggers[0].filter_has_any_storage_paths).toEqual([18])
    expect(formValues.triggers[0].filter_has_not_storage_paths).toEqual([15])
  })

  it('should reuse filter type options and update disabled state', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup
    component.addFilter(triggerGroup)

    const optionsFirst = component.getFilterTypeOptions(triggerGroup, 0)
    const optionsSecond = component.getFilterTypeOptions(triggerGroup, 0)
    expect(optionsFirst).toBe(optionsSecond)

    // to force disabled flag
    component.addFilter(triggerGroup)
    const filterArray = component.getFiltersFormArray(triggerGroup)
    const firstFilter = filterArray.at(0)
    firstFilter.get('type').setValue(TriggerFilterType.CorrespondentIs)

    component.addFilter(triggerGroup)
    const updatedFilters = component.getFiltersFormArray(triggerGroup)
    const secondFilter = updatedFilters.at(1)
    const options = component.getFilterTypeOptions(triggerGroup, 1)
    const correspondentIsOption = options.find(
      (option) => option.id === TriggerFilterType.CorrespondentIs
    )
    expect(correspondentIsOption.disabled).toBe(true)

    firstFilter.get('type').setValue(TriggerFilterType.DocumentTypeNot)
    secondFilter.get('type').setValue(TriggerFilterType.TagsAll)
    const postChangeOptions = component.getFilterTypeOptions(triggerGroup, 1)
    const correspondentOptionAfter = postChangeOptions.find(
      (option) => option.id === TriggerFilterType.CorrespondentIs
    )
    expect(correspondentOptionAfter.disabled).toBe(false)
  })

  it('should keep multi-entry filter options enabled and allow duplicates', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    component.filterDefinitions = [
      {
        id: TriggerFilterType.TagsAny,
        name: 'Any tags',
        inputType: 'tags',
        allowMultipleEntries: true,
        allowMultipleValues: true,
      } as any,
      {
        id: TriggerFilterType.CorrespondentIs,
        name: 'Correspondent is',
        inputType: 'select',
        allowMultipleEntries: false,
        allowMultipleValues: false,
        selectItems: 'correspondents',
      } as any,
    ]

    const firstFilter = component.addFilter(triggerGroup)
    firstFilter.get('type').setValue(TriggerFilterType.TagsAny)

    const secondFilter = component.addFilter(triggerGroup)
    expect(secondFilter).not.toBeNull()

    const options = component.getFilterTypeOptions(triggerGroup, 1)
    const multiEntryOption = options.find(
      (option) => option.id === TriggerFilterType.TagsAny
    )

    expect(multiEntryOption.disabled).toBe(false)
    expect(component.canAddFilter(triggerGroup)).toBe(true)
  })

  it('should return null when no filter definitions remain available', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    component.filterDefinitions = [
      {
        id: TriggerFilterType.TagsAny,
        name: 'Any tags',
        inputType: 'tags',
        allowMultipleEntries: false,
        allowMultipleValues: true,
      } as any,
      {
        id: TriggerFilterType.CorrespondentIs,
        name: 'Correspondent is',
        inputType: 'select',
        allowMultipleEntries: false,
        allowMultipleValues: false,
        selectItems: 'correspondents',
      } as any,
    ]

    const firstFilter = component.addFilter(triggerGroup)
    firstFilter.get('type').setValue(TriggerFilterType.TagsAny)
    const secondFilter = component.addFilter(triggerGroup)
    secondFilter.get('type').setValue(TriggerFilterType.CorrespondentIs)

    expect(component.canAddFilter(triggerGroup)).toBe(false)
    expect(component.addFilter(triggerGroup)).toBeNull()
  })

  it('should skip filter definitions without handlers when building form array', () => {
    const originalDefinitions = component.filterDefinitions
    component.filterDefinitions = [
      {
        id: 999,
        name: 'Unsupported',
        inputType: 'text',
        allowMultipleEntries: false,
        allowMultipleValues: false,
      } as any,
    ]

    const trigger = {
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
    } as any

    const filters = component['buildFiltersFormArray'](trigger)
    expect(filters.length).toBe(0)

    component.filterDefinitions = originalDefinitions
  })

  it('should return null when adding filter for unknown trigger form group', () => {
    expect(component.addFilter(new FormGroup({}) as any)).toBeNull()
  })

  it('should ignore remove filter calls for unknown trigger form group', () => {
    expect(() =>
      component.removeFilter(new FormGroup({}) as any, 0)
    ).not.toThrow()
  })

  it('should teardown custom field query model when removing a custom field filter', () => {
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    component.addFilter(triggerGroup)
    const filters = component.getFiltersFormArray(triggerGroup)
    const filterGroup = filters.at(0) as FormGroup
    filterGroup.get('type').setValue(TriggerFilterType.CustomFieldQuery)

    const model = component.getCustomFieldQueryModel(filterGroup)
    expect(model).toBeDefined()
    expect(
      component['getStoredCustomFieldQueryModel'](filterGroup as any)
    ).toBe(model)

    component.removeFilter(triggerGroup, 0)
    expect(
      component['getStoredCustomFieldQueryModel'](filterGroup as any)
    ).toBeNull()
  })

  it('should return readable filter names', () => {
    expect(component.getFilterName(TriggerFilterType.TagsAny)).toBe(
      'Has any of these tags'
    )
    expect(component.getFilterName(999 as any)).toBe('')
  })

  it('should build filter form array from existing trigger filters', () => {
    const trigger = workflow.triggers[0]
    trigger.filter_has_tags = [1]
    trigger.filter_has_all_tags = [2, 3]
    trigger.filter_has_not_tags = [4]
    trigger.filter_has_any_correspondents = [10] as any
    trigger.filter_has_correspondent = 5 as any
    trigger.filter_has_not_correspondents = [6] as any
    trigger.filter_has_document_type = 7 as any
    trigger.filter_has_any_document_types = [11] as any
    trigger.filter_has_not_document_types = [8] as any
    trigger.filter_has_storage_path = 9 as any
    trigger.filter_has_any_storage_paths = [12] as any
    trigger.filter_has_not_storage_paths = [10] as any
    trigger.filter_custom_field_query = JSON.stringify([
      'AND',
      [[1, 'exact', 'value']],
    ]) as any

    component.object = workflow
    component.ngOnInit()
    const triggerGroup = component.triggerFields.at(0) as FormGroup
    const filters = component.getFiltersFormArray(triggerGroup)
    expect(filters.length).toBe(13)
    const customFieldFilter = filters.at(12) as FormGroup
    expect(customFieldFilter.get('type').value).toBe(
      TriggerFilterType.CustomFieldQuery
    )
    const model = component.getCustomFieldQueryModel(customFieldFilter)
    expect(model.isValid()).toBe(true)
  })

  it('should expose select metadata helpers', () => {
    expect(component.isSelectMultiple(TriggerFilterType.CorrespondentAny)).toBe(
      true
    )
    expect(component.isSelectMultiple(TriggerFilterType.CorrespondentNot)).toBe(
      true
    )
    expect(component.isSelectMultiple(TriggerFilterType.CorrespondentIs)).toBe(
      false
    )
    expect(component.isSelectMultiple(TriggerFilterType.DocumentTypeAny)).toBe(
      true
    )
    expect(component.isSelectMultiple(TriggerFilterType.DocumentTypeIs)).toBe(
      false
    )
    expect(component.isSelectMultiple(TriggerFilterType.StoragePathAny)).toBe(
      true
    )
    expect(component.isSelectMultiple(TriggerFilterType.StoragePathIs)).toBe(
      false
    )

    component.correspondents = [{ id: 1, name: 'C1' } as any]
    component.documentTypes = [{ id: 2, name: 'DT' } as any]
    component.storagePaths = [{ id: 3, name: 'SP' } as any]

    expect(
      component.getFilterSelectItems(TriggerFilterType.CorrespondentIs)
    ).toEqual(component.correspondents)
    expect(
      component.getFilterSelectItems(TriggerFilterType.DocumentTypeIs)
    ).toEqual(component.documentTypes)
    expect(
      component.getFilterSelectItems(TriggerFilterType.DocumentTypeAny)
    ).toEqual(component.documentTypes)
    expect(
      component.getFilterSelectItems(TriggerFilterType.StoragePathIs)
    ).toEqual(component.storagePaths)
    expect(
      component.getFilterSelectItems(TriggerFilterType.StoragePathAny)
    ).toEqual(component.storagePaths)
    expect(component.getFilterSelectItems(TriggerFilterType.TagsAll)).toEqual(
      []
    )

    expect(
      component.isCustomFieldQueryFilter(TriggerFilterType.CustomFieldQuery)
    ).toBe(true)
  })

  it('should return empty select items when definition is missing', () => {
    const originalDefinitions = component.filterDefinitions
    component.filterDefinitions = []

    expect(
      component.getFilterSelectItems(TriggerFilterType.CorrespondentIs)
    ).toEqual([])

    component.filterDefinitions = originalDefinitions
  })

  it('should return empty select items when definition has unknown source', () => {
    const originalDefinitions = component.filterDefinitions
    component.filterDefinitions = [
      {
        id: TriggerFilterType.CorrespondentIs,
        name: 'Correspondent is',
        inputType: 'select',
        allowMultipleEntries: false,
        allowMultipleValues: false,
        selectItems: 'unknown',
      } as any,
    ]

    expect(
      component.getFilterSelectItems(TriggerFilterType.CorrespondentIs)
    ).toEqual([])

    component.filterDefinitions = originalDefinitions
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

    expect(component.isCustomFieldQueryValid(formGroup)).toBe(true)
    component['setCustomFieldQueryModel'](formGroup as any, model as any)

    const validSpy = jest.spyOn(model, 'isValid').mockReturnValue(false)
    const emptySpy = jest.spyOn(model, 'isEmpty').mockReturnValue(false)
    expect(component.isCustomFieldQueryValid(formGroup)).toBe(false)
    expect(validSpy).toHaveBeenCalled()

    validSpy.mockReturnValue(true)
    emptySpy.mockReturnValue(true)
    expect(component.isCustomFieldQueryValid(formGroup)).toBe(true)

    emptySpy.mockReturnValue(false)
    expect(component.isCustomFieldQueryValid(formGroup)).toBe(true)

    component['clearCustomFieldQueryModel'](formGroup as any)
  })

  it('should recover from invalid custom field query json and update control on changes', () => {
    const filterGroup = new FormGroup({
      values: new FormControl('not-json'),
    })

    component['ensureCustomFieldQueryModel'](filterGroup, 'not-json')

    const model = component['getStoredCustomFieldQueryModel'](
      filterGroup as any
    )
    expect(model).toBeDefined()
    expect(model.queries.length).toBeGreaterThan(0)

    const valuesControl = filterGroup.get('values')
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

    component['clearCustomFieldQueryModel'](filterGroup as any)
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

  it('should normalize filter values for single and multi selects', () => {
    expect(
      component['normalizeFilterValue'](TriggerFilterType.TagsAny)
    ).toEqual([])
    expect(
      component['normalizeFilterValue'](TriggerFilterType.TagsAny, 5)
    ).toEqual([5])
    expect(
      component['normalizeFilterValue'](TriggerFilterType.TagsAny, [5, 6])
    ).toEqual([5, 6])
    expect(
      component['normalizeFilterValue'](TriggerFilterType.CorrespondentIs, [7])
    ).toEqual(7)
    expect(
      component['normalizeFilterValue'](TriggerFilterType.CorrespondentIs, 8)
    ).toEqual(8)
    const customFieldJson = JSON.stringify(['AND', [[1, 'exact', 'test']]])
    expect(
      component['normalizeFilterValue'](
        TriggerFilterType.CustomFieldQuery,
        customFieldJson
      )
    ).toEqual(customFieldJson)

    const customFieldObject = ['AND', [[1, 'exact', 'other']]]
    expect(
      component['normalizeFilterValue'](
        TriggerFilterType.CustomFieldQuery,
        customFieldObject
      )
    ).toEqual(JSON.stringify(customFieldObject))

    expect(
      component['normalizeFilterValue'](
        TriggerFilterType.CustomFieldQuery,
        false
      )
    ).toBeNull()
  })

  it('should add and remove filter form groups', () => {
    component['changeDetector'] = { detectChanges: jest.fn() } as any
    component.object = undefined
    component.addTrigger()
    const triggerGroup = component.triggerFields.at(0) as FormGroup

    component.addFilter(triggerGroup)

    component.removeFilter(triggerGroup, 0)
    expect(component.getFiltersFormArray(triggerGroup).length).toBe(0)

    component.addFilter(triggerGroup)
    const filterArrayAfterAdd = component.getFiltersFormArray(triggerGroup)
    filterArrayAfterAdd.at(0).get('type').setValue(TriggerFilterType.TagsAll)
    expect(component.getFiltersFormArray(triggerGroup).length).toBe(1)
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

  it('should handle parsing of passwords from array to string and back on save', () => {
    const passwordAction: WorkflowAction = {
      id: 1,
      type: WorkflowActionType.PasswordRemoval,
      passwords: ['pass1', 'pass2'],
    }
    component.object = {
      name: 'Workflow with Passwords',
      id: 1,
      order: 1,
      enabled: true,
      triggers: [],
      actions: [passwordAction],
    }
    component.ngOnInit()

    const formActions = component.objectForm.get('actions') as FormArray
    expect(formActions.value[0].passwords).toBe('pass1\npass2')
    formActions.at(0).get('passwords').setValue('pass1\npass2\npass3')
    component.save()

    expect(component.objectForm.get('actions').value[0].passwords).toEqual([
      'pass1',
      'pass2',
      'pass3',
    ])
  })
})
