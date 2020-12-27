import { Component, EventEmitter, Input, Output, OnInit, OnDestroy } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { NgbDateParserFormatter } from '@ng-bootstrap/ng-bootstrap';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { FilterRule } from 'src/app/data/filter-rule';
import { FILTER_ADDED_AFTER, FILTER_ADDED_BEFORE, FILTER_CORRESPONDENT, FILTER_CREATED_AFTER, FILTER_CREATED_BEFORE, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_RULE_TYPES, FILTER_TITLE } from 'src/app/data/filter-rule-type';
import { DateSelection } from 'src/app/components/common/date-dropdown/date-dropdown.component';

@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss']
})
export class FilterEditorComponent implements OnInit, OnDestroy {

  generateFilterName() {
    if (this.filterRules.length == 1) {
      let rule = this.filterRules[0]
      switch(this.filterRules[0].rule_type) {

        case FILTER_CORRESPONDENT:
          return `Correspondent: ${this.correspondents.find(c => c.id == +rule.value)?.name}`

        case FILTER_DOCUMENT_TYPE:
          return `Type: ${this.documentTypes.find(dt => dt.id == +rule.value)?.name}`

        case FILTER_HAS_TAG:
          return `Tag: ${this.tags.find(t => t.id == +rule.value)?.name}`

      }
    }

    return ""
  }

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService
  ) { }

  tags: PaperlessTag[] = []
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[] = []

  @Input()
  filterRules: FilterRule[]

  @Output()
  filterRulesChange = new EventEmitter<FilterRule[]>()

  hasFilters() {
    return this.filterRules.length > 0
  }

  get selectedTags(): PaperlessTag[] {
    let tagRules: FilterRule[] = this.filterRules.filter(fr => fr.rule_type == FILTER_HAS_TAG)
    return this.tags?.filter(t => tagRules.find(tr => +tr.value == t.id))
  }

  get selectedCorrespondents(): PaperlessCorrespondent[] {
    let correspondentRules: FilterRule[] = this.filterRules.filter(fr => fr.rule_type == FILTER_CORRESPONDENT)
    return this.correspondents?.filter(c => correspondentRules.find(cr => +cr.value == c.id))
  }

  get selectedDocumentTypes(): PaperlessDocumentType[] {
    let documentTypeRules: FilterRule[] = this.filterRules.filter(fr => fr.rule_type == FILTER_DOCUMENT_TYPE)
    return this.documentTypes?.filter(dt => documentTypeRules.find(dtr => +dtr.value == dt.id))
  }

  get titleFilter() {
    let existingRule = this.filterRules.find(rule => rule.rule_type == FILTER_TITLE)
    return existingRule ? existingRule.value : ''
  }

  set titleFilter(value) {
    this.titleFilterDebounce.next(value)
  }

  titleFilterDebounce: Subject<string>
  subscription: Subscription

  ngOnInit() {
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.correspondentService.listAll().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)

    this.titleFilterDebounce = new Subject<string>()

    this.subscription = this.titleFilterDebounce.pipe(
      debounceTime(400),
      distinctUntilChanged()
    ).subscribe(title => {
      this.setTitleRule(title)
    })
  }

  ngOnDestroy() {
    this.titleFilterDebounce.complete()
    // TODO: not sure if both is necessary
    this.subscription.unsubscribe()
  }

  applyFilters() {
    this.filterRulesChange.next(this.filterRules)
  }

  clearSelected() {
    this.filterRules = []
    this.applyFilters()
  }

  private toggleFilterRule(filterRuleTypeID: number, value: number) {

    let filterRuleType = FILTER_RULE_TYPES.find(t => t.id == filterRuleTypeID)

    let existingRule = this.filterRules.find(rule => rule.rule_type == filterRuleTypeID && rule.value == value?.toString())
    let existingRuleOfSameType = this.filterRules.find(rule => rule.rule_type == filterRuleTypeID)

    if (existingRule) {
      // if this exact rule already exists, remove it in all cases.
      this.filterRules.splice(this.filterRules.indexOf(existingRule), 1)
    } else if (filterRuleType.multi || !existingRuleOfSameType) {
      // if we allow multiple rules per type, or no rule of this type already exists, push a new rule.
      this.filterRules.push({rule_type: filterRuleTypeID, value: value?.toString()})
    } else {
      // otherwise (i.e., no multi support AND there's already a rule of this type), update the rule.
      existingRuleOfSameType.value = value?.toString()
    }
    this.applyFilters()
  }

  private setTitleRule(title: string) {
    let existingRule = this.filterRules.find(rule => rule.rule_type == FILTER_TITLE)

    if (!existingRule && title) {
      this.filterRules.push({rule_type: FILTER_TITLE, value: title})
    } else if (existingRule && !title) {
      this.filterRules.splice(this.filterRules.findIndex(rule => rule.rule_type == FILTER_TITLE), 1)
    } else if (existingRule && title) {
      existingRule.value = title
    }
    this.applyFilters()
  }

  toggleTag(tagId: number) {
    this.toggleFilterRule(FILTER_HAS_TAG, tagId)
  }

  toggleCorrespondent(correspondentId: number) {
    this.toggleFilterRule(FILTER_CORRESPONDENT, correspondentId)
  }

  toggleDocumentType(documentTypeId: number) {
    this.toggleFilterRule(FILTER_DOCUMENT_TYPE, documentTypeId)
  }



  // Date handling


  onDatesCreatedSet(dates: DateSelection) {
    this.setDateCreatedBefore(dates.before)
    this.setDateCreatedAfter(dates.after)
    this.applyFilters()
  }

  onDatesAddedSet(dates: DateSelection) {
    this.setDateAddedBefore(dates.before)
    this.setDateAddedAfter(dates.after)
    this.applyFilters()
  }

  get dateCreatedBefore(): string {
    let createdBeforeRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_CREATED_BEFORE)
    return createdBeforeRule ? createdBeforeRule.value : null
  }

  get dateCreatedAfter(): string {
    let createdAfterRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_CREATED_AFTER)
    return createdAfterRule ? createdAfterRule.value : null
  }

  get dateAddedBefore(): string {
    let addedBeforeRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_ADDED_BEFORE)
    return addedBeforeRule ? addedBeforeRule.value : null
  }

  get dateAddedAfter(): string {
    let addedAfterRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_ADDED_AFTER)
    return addedAfterRule ? addedAfterRule.value : null
  }

  setDateCreatedBefore(date?: string) {
    if (date) this.setDateFilter(date, FILTER_CREATED_BEFORE)
    else this.clearDateFilter(FILTER_CREATED_BEFORE)
  }

  setDateCreatedAfter(date?: string) {
    if (date) this.setDateFilter(date, FILTER_CREATED_AFTER)
    else this.clearDateFilter(FILTER_CREATED_AFTER)
  }

  setDateAddedBefore(date?: string) {
    if (date) this.setDateFilter(date, FILTER_ADDED_BEFORE)
    else this.clearDateFilter(FILTER_ADDED_BEFORE)
  }

  setDateAddedAfter(date?: string) {
    if (date) this.setDateFilter(date, FILTER_ADDED_AFTER)
    else this.clearDateFilter(FILTER_ADDED_AFTER)
  }

  setDateFilter(date: string, dateRuleTypeID: number) {
    let existingRule = this.filterRules.find(rule => rule.rule_type == dateRuleTypeID)

    if (existingRule) {
      existingRule.value = date
    } else {
      this.filterRules.push({rule_type: dateRuleTypeID, value: date})
    }
  }

  clearDateFilter(dateRuleTypeID: number) {
    let ruleIndex = this.filterRules.findIndex(rule => rule.rule_type == dateRuleTypeID)
    if (ruleIndex != -1) {
      this.filterRules.splice(ruleIndex, 1)
    }
  }

}
