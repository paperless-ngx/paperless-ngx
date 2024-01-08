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
import {
  DocumentSource,
  WorkflowTrigger,
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
]

export const WORKFLOW_ACTION_OPTIONS = [
  {
    id: WorkflowActionType.Assignment,
    name: $localize`Assignment`,
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

  templates: Workflow[]
  correspondents: Correspondent[]
  documentTypes: DocumentType[]
  storagePaths: StoragePath[]
  mailRules: MailRule[]
  customFields: CustomField[]

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
    customFieldsService: CustomFieldsService
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
      filter_has_correspondent: null,
      filter_has_document_type: null,
      matching_algorithm: MATCH_NONE,
      match: '',
      is_insensitive: true,
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
  }
}
