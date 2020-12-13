import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { FilterRule } from 'src/app/data/filter-rule';
import { FilterRuleType, FILTER_RULE_TYPES, FILTER_CORRESPONDENT, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_TITLE, FILTER_ADDED_BEFORE, FILTER_ADDED_AFTER, FILTER_CREATED_BEFORE, FILTER_CREATED_AFTER, FILTER_CREATED_YEAR, FILTER_CREATED_MONTH, FILTER_CREATED_DAY } from 'src/app/data/filter-rule-type';
import { Results } from 'src/app/data/results'
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { NgbDate, NgbDateStruct } from '@ng-bootstrap/ng-bootstrap';

@Injectable({
  providedIn: 'root'
})
export class FilterEditorViewService {
  private tags$: Observable<Results<PaperlessTag>>
  private correspondents$: Observable<Results<PaperlessCorrespondent>>
  private documentTypes$: Observable<Results<PaperlessDocumentType>>

  tags: PaperlessTag[] = []
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[] = []

  filterRules: FilterRule[] = []

  constructor(private tagService: TagService, private documentTypeService: DocumentTypeService, private correspondentService: CorrespondentService) {
    this.tags$ = this.tagService.listAll()
    this.tags$.subscribe(result => this.tags = result.results)
    this.correspondents$ = this.correspondentService.listAll()
    this.correspondents$.subscribe(result => this.correspondents = result.results)
    this.documentTypes$ = this.documentTypeService.listAll()
    this.documentTypes$.subscribe(result => this.documentTypes = result.results)
  }

  clear() {
    this.filterRules = []
  }

  hasFilters() {
    return this.filterRules.length > 0
  }

  set filterText(text: string) {
    let filterRules = this.filterRules
    let existingRule = filterRules.find(rule => rule.type.id == FILTER_TITLE)
    if (existingRule && existingRule.value == text) {
      return
    } else if (existingRule) {
      existingRule.value = text
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == FILTER_TITLE), value: text})
    }
    this.filterRules = filterRules
  }

  get filterText(): string {
    let existingRule = this.filterRules.find(rule => rule.type.id == FILTER_TITLE)
    return existingRule ? existingRule.value : ''
  }

  get selectedTags(): PaperlessTag[] {
    let tagRules: FilterRule[] = this.filterRules.filter(fr => fr.type.id == FILTER_HAS_TAG)
    return this.tags?.filter(t => tagRules.find(tr => tr.value == t.id))
  }

  get selectedCorrespondents(): PaperlessCorrespondent[] {
    let correspondentRules: FilterRule[] = this.filterRules.filter(fr => fr.type.id == FILTER_CORRESPONDENT)
    return this.correspondents?.filter(c => correspondentRules.find(cr => cr.value == c.id))
  }

  get selectedDocumentTypes(): PaperlessDocumentType[] {
    let documentTypeRules: FilterRule[] = this.filterRules.filter(fr => fr.type.id == FILTER_DOCUMENT_TYPE)
    return this.documentTypes?.filter(dt => documentTypeRules.find(dtr => dtr.value == dt.id))
  }

  toggleFitlerByTag(tag: PaperlessTag) {
    this.toggleFilterByItem(tag, FILTER_HAS_TAG)
  }

  toggleFitlerByCorrespondent(tag: PaperlessCorrespondent) {
    this.toggleFilterByItem(tag, FILTER_CORRESPONDENT)
  }

  toggleFitlerByDocumentType(tag: PaperlessDocumentType) {
    this.toggleFilterByItem(tag, FILTER_DOCUMENT_TYPE)
  }

  toggleFitlerByTagID(tagID: number) {
    this.toggleFitlerByTag(this.tags?.find(t => t.id == tagID))
  }

  toggleFitlerByCorrespondentID(correspondentID: number) {
    this.toggleFitlerByCorrespondent(this.correspondents?.find(t => t.id == correspondentID))
  }

  toggleFitlerByDocumentTypeID(documentTypeID: number) {
    this.toggleFitlerByDocumentType(this.documentTypes?.find(t => t.id == documentTypeID))
  }

  private toggleFilterByItem(item: ObjectWithId, filterRuleTypeID: number) {
    let filterRules = this.filterRules
    let filterRuleType: FilterRuleType = FILTER_RULE_TYPES.find(t => t.id == filterRuleTypeID)
    let existingRules = filterRules.filter(rule => rule.type.id == filterRuleType.id)
    let existingItemRule = existingRules?.find(rule => rule.value == item.id)

    if (existingRules && existingItemRule) {
      filterRules.splice(filterRules.indexOf(existingItemRule), 1) // if exact rule exists just remove
    } else if (existingRules.length > 0 && filterRuleType.multi) { // e.g. tags can have multiple
      filterRules.push({type: filterRuleType, value: item.id})
    } else if (existingRules.length > 0) { // Correspondents & DocumentTypes only one
      filterRules.find(rule => rule.type.id == filterRuleType.id).value = item.id
    } else {
      filterRules.push({type: filterRuleType, value: item.id})
    }

    this.filterRules = filterRules
  }

  get dateCreatedBefore(): NgbDateStruct {
    let createdBeforeRule: FilterRule = this.filterRules.find(fr => fr.type.id == FILTER_CREATED_BEFORE)
    return createdBeforeRule ? {
      year: createdBeforeRule.value.substring(0,4),
      month: createdBeforeRule.value.substring(5,7),
      day: createdBeforeRule.value.substring(8,10)
    } : undefined
  }

  get dateCreatedAfter(): NgbDateStruct {
    let createdAfterRule: FilterRule = this.filterRules.find(fr => fr.type.id == FILTER_CREATED_AFTER)
    return createdAfterRule ? {
      year: createdAfterRule.value.substring(0,4),
      month: createdAfterRule.value.substring(5,7),
      day: createdAfterRule.value.substring(8,10)
    } : undefined
  }

  get dateAddedBefore(): NgbDateStruct {
    let addedBeforeRule: FilterRule = this.filterRules.find(fr => fr.type.id == FILTER_ADDED_BEFORE)
    return addedBeforeRule ? {
      year: addedBeforeRule.value.substring(0,4),
      month: addedBeforeRule.value.substring(5,7),
      day: addedBeforeRule.value.substring(8,10)
    } : undefined
  }

  get dateAddedAfter(): NgbDateStruct {
    let addedAfterRule: FilterRule = this.filterRules.find(fr => fr.type.id == FILTER_ADDED_AFTER)
    return addedAfterRule ? {
      year: addedAfterRule.value.substring(0,4),
      month: addedAfterRule.value.substring(5,7),
      day: addedAfterRule.value.substring(8,10)
    } : undefined
  }

  setDateCreatedBefore(date: NgbDateStruct) {
    this.setDate(date, FILTER_CREATED_BEFORE)
  }

  setDateCreatedAfter(date: NgbDateStruct) {
    this.setDate(date, FILTER_CREATED_AFTER)
  }

  setDateAddedBefore(date: NgbDateStruct) {
    this.setDate(date, FILTER_ADDED_BEFORE)
  }

  setDateAddedAfter(date: NgbDateStruct) {
    this.setDate(date, FILTER_ADDED_AFTER)
  }

  setDate(date: NgbDateStruct, dateRuleTypeID: number) {
    let filterRules = this.filterRules
    let existingRule = filterRules.find(rule => rule.type.id == dateRuleTypeID)
    let newValue = `${date.year}-${date.month.toString().padStart(2,'0')}-${date.day.toString().padStart(2,'0')}` // YYYY-MM-DD

    if (existingRule) {
      existingRule.value = newValue
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == dateRuleTypeID), value: newValue})
    }

    this.filterRules = filterRules
  }
}
