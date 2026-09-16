import { NgTemplateOutlet } from '@angular/common'
import { Component, EventEmitter, inject, Input, Output } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  ADVANCED_SEARCH_DATE_KEYWORD_LABELS,
  ADVANCED_SEARCH_DATE_KEYWORDS,
  ADVANCED_SEARCH_DATE_OPERATOR_LABELS,
  ADVANCED_SEARCH_DATE_UNIT_LABELS,
  ADVANCED_SEARCH_FIELD_GROUPS,
  ADVANCED_SEARCH_FIELD_KINDS,
  ADVANCED_SEARCH_FIELD_LABELS,
  ADVANCED_SEARCH_MAX_ATOMS,
  ADVANCED_SEARCH_MAX_DEPTH,
  ADVANCED_SEARCH_OPERATOR_LABELS,
  ADVANCED_SEARCH_OPERATORS_BY_KIND,
  AdvancedSearchDateUnit,
  AdvancedSearchField,
  AdvancedSearchFieldKind,
  AdvancedSearchLogicalOperator,
  AdvancedSearchOperator,
  AdvancedSearchQueryAtom,
  AdvancedSearchQueryElement,
  AdvancedSearchQueryElementType,
  AdvancedSearchQueryGroup,
} from 'src/app/data/advanced-search-query'
import {
  parseAdvancedSearchQuery,
  serializeAdvancedSearchQuery,
} from 'src/app/utils/advanced-search-query'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-advanced-search-dialog',
  templateUrl: './advanced-search-dialog.component.html',
  styleUrl: './advanced-search-dialog.component.scss',
  imports: [FormsModule, NgTemplateOutlet, NgxBootstrapIconsModule],
})
export class AdvancedSearchDialogComponent extends LoadingComponentWithPermissions {
  private activeModal = inject(NgbActiveModal)

  public readonly ElementType = AdvancedSearchQueryElementType
  public readonly LogicalOperator = AdvancedSearchLogicalOperator
  public readonly Operator = AdvancedSearchOperator
  public readonly FieldKind = AdvancedSearchFieldKind
  public readonly fieldGroups = ADVANCED_SEARCH_FIELD_GROUPS
  public readonly fieldLabels = ADVANCED_SEARCH_FIELD_LABELS
  public readonly dateKeywords = ADVANCED_SEARCH_DATE_KEYWORDS
  public readonly dateKeywordLabels = ADVANCED_SEARCH_DATE_KEYWORD_LABELS
  public readonly dateUnits = Object.values(AdvancedSearchDateUnit)
  public readonly dateUnitLabels = ADVANCED_SEARCH_DATE_UNIT_LABELS
  public readonly maxDepth = ADVANCED_SEARCH_MAX_DEPTH
  public readonly maxAtoms = ADVANCED_SEARCH_MAX_ATOMS

  @Output()
  public queryApplied = new EventEmitter<string>()

  public root: AdvancedSearchQueryGroup = this.emptyRoot()

  // True when the query in the search box uses syntax the editor cannot show
  public unreadable: boolean = false

  private _query: string = ''

  @Input()
  set query(query: string) {
    this._query = query ?? ''
    const parsed = parseAdvancedSearchQuery(this._query)
    this.unreadable = !!this._query.trim() && !parsed
    this.root = parsed ?? this.emptyRoot()
  }

  get query(): string {
    return this._query
  }

  constructor() {
    super()
    this.loading.set(false)
  }

  // Stable ids for the radio groups, without putting them in the query model
  private ids = new WeakMap<object, number>()
  private nextId = 0

  public idFor(element: AdvancedSearchQueryElement): number {
    if (!this.ids.has(element)) {
      this.ids.set(element, this.nextId++)
    }
    return this.ids.get(element)
  }

  private emptyRoot(): AdvancedSearchQueryGroup {
    return {
      type: AdvancedSearchQueryElementType.Group,
      operator: AdvancedSearchLogicalOperator.And,
      children: [this.newAtom()],
    }
  }

  private newAtom(): AdvancedSearchQueryAtom {
    return {
      type: AdvancedSearchQueryElementType.Atom,
      field: AdvancedSearchField.Content,
      operator: AdvancedSearchOperator.AllWords,
      value: '',
    }
  }

  public get generatedQuery(): string {
    return serializeAdvancedSearchQuery(this.root)
  }

  public kindOf(atom: AdvancedSearchQueryAtom): AdvancedSearchFieldKind {
    return ADVANCED_SEARCH_FIELD_KINDS[atom.field]
  }

  public operatorsFor(atom: AdvancedSearchQueryAtom): AdvancedSearchOperator[] {
    return ADVANCED_SEARCH_OPERATORS_BY_KIND[this.kindOf(atom)]
  }

  public operatorLabel(
    atom: AdvancedSearchQueryAtom,
    operator: AdvancedSearchOperator
  ): string {
    return this.kindOf(atom) === AdvancedSearchFieldKind.Date
      ? (ADVANCED_SEARCH_DATE_OPERATOR_LABELS[operator] ??
          ADVANCED_SEARCH_OPERATOR_LABELS[operator])
      : ADVANCED_SEARCH_OPERATOR_LABELS[operator]
  }

  public placeholderFor(atom: AdvancedSearchQueryAtom): string {
    switch (atom.operator) {
      case AdvancedSearchOperator.Phrase:
        return $localize`phrase`
      case AdvancedSearchOperator.StartsWith:
        return $localize`beginning of a word`
      default:
        return $localize`words`
    }
  }

  public onFieldChange(atom: AdvancedSearchQueryAtom) {
    // Keep the condition only if the new field still offers it
    if (!this.operatorsFor(atom).includes(atom.operator)) {
      atom.operator = this.operatorsFor(atom)[0]
    }
    this.clearValues(atom)
  }

  public onOperatorChange(atom: AdvancedSearchQueryAtom) {
    this.clearValues(atom)
  }

  private clearValues(atom: AdvancedSearchQueryAtom) {
    atom.value = ''
    atom.valueTo = undefined
    atom.unit =
      atom.operator === AdvancedSearchOperator.WithinLast
        ? AdvancedSearchDateUnit.Day
        : undefined
  }

  public addAtom(group: AdvancedSearchQueryGroup) {
    group.children.push(this.newAtom())
  }

  public addGroup(group: AdvancedSearchQueryGroup) {
    group.children.push({
      type: AdvancedSearchQueryElementType.Group,
      operator: AdvancedSearchLogicalOperator.Or,
      children: [this.newAtom()],
    })
  }

  public remove(
    parent: AdvancedSearchQueryGroup,
    element: AdvancedSearchQueryElement
  ) {
    parent.children = parent.children.filter((child) => child !== element)
  }

  public startOver() {
    this.unreadable = false
    this.root = this.emptyRoot()
  }

  public apply() {
    this.queryApplied.emit(this.generatedQuery)
    this.activeModal.close()
  }

  public cancel() {
    this.activeModal.close()
  }
}
