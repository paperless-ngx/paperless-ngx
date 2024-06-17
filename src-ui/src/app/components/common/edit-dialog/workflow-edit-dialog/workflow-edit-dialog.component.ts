import { Component, OnInit } from '@angular/core'
import { FormGroup, FormControl, FormArray } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { Workflow } from 'src/app/data/workflow'
import { Correspondent } from 'src/app/data/correspondent'
import { DocumentType } from 'src/app/data/document-type'
import { StoragePath } from 'src/app/data/storage-path'
import { WorkflowService } from 'src/app/services/rest/workflow.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent } from '../edit-dialog.component'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'
import { MailRule } from 'src/app/data/mail-rule'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { CustomField } from 'src/app/data/custom-field'
import { GroupService } from 'src/app/services/rest/group.service'
import { Group } from 'src/app/data/group'
import {
  DocumentSource,
  WorkflowTrigger,
  WorkflowTriggerAccessType,
  WorkflowTriggerStatus,
  WorkflowTriggerType,
} from 'src/app/data/workflow-trigger'
import {
  WorkflowAction,
  WorkflowActionType,
} from 'src/app/data/workflow-action'
import { CdkDragDrop, moveItemInArray } from '@angular/cdk/drag-drop'
import {
  MATCHING_ALGORITHMS,
  MATCH_AUTO,
  MATCH_NONE,
} from 'src/app/data/matching-model'
import { ContentType } from 'src/app/data/content-type'
import { ContentTypeService } from 'src/app/services/rest/content-type.service'

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
    id: WorkflowTriggerType.ApprovalAdded,
    name: $localize`Approval Added`,
  },
  {
    id: WorkflowTriggerType.ApprovalUpdated,
    name: $localize`Approval Updated`,
  },
]

export const WORKFLOW_STATUS_OPTIONS = [
  {
    id: WorkflowTriggerStatus.Pending,
    name: $localize`Pending`,
  },
  {
    id: WorkflowTriggerStatus.Success,
    name: $localize`Success`,
  },
  {
    id: WorkflowTriggerStatus.Failure,
    name: $localize`Failure`,
  },
  {
    id: WorkflowTriggerStatus.Revoked,
    name: $localize`Revoked`,
  },
]

export const WORKFLOW_ACCESS_TYPES_OPTIONS = [
  {
    id: WorkflowTriggerAccessType.Owner,
    name: $localize`Owner`,
  },
  {
    id: WorkflowTriggerAccessType.Edit,
    name: $localize`Edit`,
  },
  {
    id: WorkflowTriggerAccessType.View,
    name: $localize`View`,
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
    id: WorkflowActionType.Assignment_with_approval,
    name: $localize`Assignment with approval`,
  },
  {
    id: WorkflowActionType.Removal_with_approval,
    name: $localize`Removal with approval`,
  },
]

const TRIGGER_MATCHING_ALGORITHMS = MATCHING_ALGORITHMS.filter(
  (a) => a.id !== MATCH_AUTO
)

@Component({
  selector: 'pngx-workflow-edit-dialog',
  templateUrl: './workflow-edit-dialog.component.html',
  styleUrls: ['./workflow-edit-dialog.component.scss'],
})
export class WorkflowEditDialogComponent
  extends EditDialogComponent<Workflow>
  implements OnInit
{
  public WorkflowTriggerType = WorkflowTriggerType
  public WorkflowActionType = WorkflowActionType

  templates: Workflow[]
  correspondents: Correspondent[]
  documentTypes: DocumentType[]
  storagePaths: StoragePath[]
  mailRules: MailRule[]
  customFields: CustomField[]
  groups: Group[]
  contentTypes: ContentType[]


  expandedItem: number = null

  constructor(
    service: WorkflowService,
    activeModal: NgbActiveModal,
    correspondentService: CorrespondentService,
    documentTypeService: DocumentTypeService,
    storagePathService: StoragePathService,
    mailRuleService: MailRuleService,
    userService: UserService,
    settingsService: SettingsService,
    customFieldsService: CustomFieldsService,
    groupService: GroupService,
    contentTypeService: ContentTypeService
  ) {
    super(service, activeModal, userService, settingsService)

    correspondentService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.correspondents = result.results))

    documentTypeService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.documentTypes = result.results))

    storagePathService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.storagePaths = result.results))

    mailRuleService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.mailRules = result.results))

    customFieldsService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.customFields = result.results))
    
    groupService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.groups = result.results))

    contentTypeService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.contentTypes = result))
    console.log(contentTypeService)
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
        filter_has_tags: new FormControl(trigger.filter_has_tags),
        filter_has_correspondent: new FormControl(
          trigger.filter_has_correspondent
        ),
        filter_has_document_type: new FormControl(
          trigger.filter_has_document_type
        ),
        filter_has_groups: new FormControl(trigger.filter_has_groups),
        filter_has_status: new FormControl(trigger.filter_has_status),
        filter_has_content_type: new FormControl(trigger.filter_has_content_type),
        filter_has_access_type: new FormControl(trigger.filter_has_access_type),
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
        assign_content_type: new FormControl(action.assign_content_type),
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
      }),
      { emitEvent }
    )
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

  get triggerStatusOptions() {
    return WORKFLOW_STATUS_OPTIONS
  }

  get triggerAccesTypesOptions() {
    return WORKFLOW_ACCESS_TYPES_OPTIONS
  }

  getTriggerTypeOptionName(type: WorkflowTriggerType): string {
    return this.triggerTypeOptions.find((t) => t.id === type)?.name ?? ''
  }

  getTriggerStatusOptionName(status: WorkflowTriggerStatus): string {
    return this.triggerStatusOptions.find((t) => t.id === status)?.name ?? ''
  }

  getTriggerAccessTypesOptionName(access_types: WorkflowTriggerAccessType): string {
    return this.triggerAccesTypesOptions.find((t) => t.id === access_types)?.name ?? ''
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
      filter_has_correspondent: null,
      filter_has_document_type: null,
      matching_algorithm: MATCH_NONE,
      match: '',
      is_insensitive: true,
      filter_has_groups: [],
      filter_has_status: WorkflowTriggerStatus.Pending,
      filter_has_content_type: null,
      filter_has_access_type: WorkflowTriggerAccessType.View
    }
    this.object.triggers.push(trigger)
    this.createTriggerField(trigger)
  }

  get actionTypeOptions() {
    return WORKFLOW_ACTION_OPTIONS
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
      assign_content_type: null,
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
    // removing id will effectively re-create the actions in this order
    this.object.actions.forEach((a) => (a.id = null))
    this.actionFields.controls.forEach((c) =>
      c.get('id').setValue(null, { emitEvent: false })
    )
  }
}
