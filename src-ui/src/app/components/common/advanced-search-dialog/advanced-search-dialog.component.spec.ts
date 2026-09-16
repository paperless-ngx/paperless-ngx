import { ComponentFixture, TestBed } from '@angular/core/testing'

import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  AdvancedSearchDateUnit,
  AdvancedSearchField,
  AdvancedSearchLogicalOperator,
  AdvancedSearchOperator,
  AdvancedSearchQueryAtom,
  AdvancedSearchQueryElementType,
  AdvancedSearchQueryGroup,
} from 'src/app/data/advanced-search-query'
import { AdvancedSearchDialogComponent } from './advanced-search-dialog.component'

describe('AdvancedSearchDialogComponent', () => {
  let component: AdvancedSearchDialogComponent
  let fixture: ComponentFixture<AdvancedSearchDialogComponent>
  let activeModal: NgbActiveModal

  const firstAtom = (): AdvancedSearchQueryAtom =>
    component.root.children[0] as AdvancedSearchQueryAtom

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        AdvancedSearchDialogComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [NgbActiveModal],
    }).compileComponents()

    fixture = TestBed.createComponent(AdvancedSearchDialogComponent)
    activeModal = TestBed.inject(NgbActiveModal)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should start with one empty condition and nothing to search for', () => {
    expect(component.root.children).toHaveLength(1)
    expect(component.generatedQuery).toBe('')
    expect(component.unreadable).toBeFalsy()
  })

  it('should show an existing query as conditions', () => {
    component.query = 'title:invoice AND NOT tag:paid'
    expect(component.unreadable).toBeFalsy()
    expect(component.root.children).toHaveLength(2)
    expect(component.generatedQuery).toBe('title:invoice AND NOT tag:paid')
  })

  it('should flag a query it cannot show and start empty', () => {
    component.query = 'title:invoice^2'
    expect(component.unreadable).toBeTruthy()
    expect(component.generatedQuery).toBe('')
  })

  it('should clear the warning when starting a new query', () => {
    component.query = 'title:invoice^2'
    component.startOver()
    expect(component.unreadable).toBeFalsy()
    expect(component.root.children).toHaveLength(1)
  })

  it('should treat an empty query as a fresh start', () => {
    component.query = '   '
    expect(component.unreadable).toBeFalsy()
    expect(component.root.children).toHaveLength(1)
  })

  it('should write the query as conditions are filled in', () => {
    const atom = firstAtom()
    atom.field = AdvancedSearchField.Title
    atom.value = 'unpaid invoice'
    expect(component.generatedQuery).toBe('title:unpaid AND title:invoice')
  })

  it('should offer the conditions of the chosen field', () => {
    const atom = firstAtom()
    atom.field = AdvancedSearchField.Added
    component.onFieldChange(atom)
    expect(component.operatorsFor(atom)).toContain(
      AdvancedSearchOperator.WithinLast
    )
    expect(component.operatorsFor(atom)).not.toContain(
      AdvancedSearchOperator.Phrase
    )
  })

  it('should keep a condition the new field still offers', () => {
    const atom = firstAtom()
    atom.operator = AdvancedSearchOperator.Phrase
    atom.field = AdvancedSearchField.Correspondent
    component.onFieldChange(atom)
    expect(atom.operator).toBe(AdvancedSearchOperator.Phrase)
  })

  it('should replace a condition the new field does not offer, and clear the value', () => {
    const atom = firstAtom()
    atom.operator = AdvancedSearchOperator.Phrase
    atom.value = 'invoice'
    atom.field = AdvancedSearchField.ASN
    component.onFieldChange(atom)
    expect(atom.operator).toBe(AdvancedSearchOperator.Equals)
    expect(atom.value).toBe('')
  })

  it('should give a within-the-last condition a unit to start from', () => {
    const atom = firstAtom()
    atom.field = AdvancedSearchField.Added
    atom.operator = AdvancedSearchOperator.WithinLast
    component.onOperatorChange(atom)
    expect(atom.unit).toBe(AdvancedSearchDateUnit.Day)
    atom.value = '3'
    expect(component.generatedQuery).toBe('added:[-3 days to now]')
  })

  it('should label date comparisons as dates', () => {
    const atom = firstAtom()
    atom.field = AdvancedSearchField.Created
    expect(
      component.operatorLabel(atom, AdvancedSearchOperator.AtLeast)
    ).toEqual('is on or after')
    atom.field = AdvancedSearchField.ASN
    expect(
      component.operatorLabel(atom, AdvancedSearchOperator.AtLeast)
    ).toEqual('is at least')
  })

  it('should add and remove conditions', () => {
    component.addAtom(component.root)
    expect(component.root.children).toHaveLength(2)
    component.remove(component.root, component.root.children[1])
    expect(component.root.children).toHaveLength(1)
  })

  it('should add a group, which starts as Any', () => {
    component.addGroup(component.root)
    const group = component.root.children[1] as AdvancedSearchQueryGroup
    expect(group.type).toBe(AdvancedSearchQueryElementType.Group)
    expect(group.operator).toBe(AdvancedSearchLogicalOperator.Or)
    expect(group.children).toHaveLength(1)
  })

  it('should give every group its own id, once', () => {
    component.addGroup(component.root)
    const group = component.root.children[1] as AdvancedSearchQueryGroup
    expect(component.idFor(component.root)).not.toEqual(component.idFor(group))
    expect(component.idFor(group)).toEqual(component.idFor(group))
  })

  it('should apply the query and close', () => {
    const emitSpy = jest.spyOn(component.queryApplied, 'emit')
    const closeSpy = jest.spyOn(activeModal, 'close')
    const atom = firstAtom()
    atom.value = 'invoice'
    component.apply()
    expect(emitSpy).toHaveBeenCalledWith('content:invoice')
    expect(closeSpy).toHaveBeenCalled()
  })

  it('should close without applying on cancel', () => {
    const emitSpy = jest.spyOn(component.queryApplied, 'emit')
    const closeSpy = jest.spyOn(activeModal, 'close')
    component.cancel()
    expect(emitSpy).not.toHaveBeenCalled()
    expect(closeSpy).toHaveBeenCalled()
  })

  it('should show the query it will apply', () => {
    component.query = 'content:invoice OR content:receipt'
    fixture.detectChanges()
    const preview = fixture.nativeElement.querySelector(
      '#advanced-search-preview'
    )
    expect(preview.textContent).toContain('content:invoice OR content:receipt')
  })

  it('should not offer to apply an empty query', () => {
    fixture.detectChanges()
    const apply = Array.from(
      fixture.nativeElement.querySelectorAll('.modal-footer button')
    ).pop() as HTMLButtonElement
    expect(apply.disabled).toBeTruthy()
  })
})
