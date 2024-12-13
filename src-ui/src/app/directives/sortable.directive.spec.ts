import { Component, DebugElement } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { SortEvent, SortableDirective } from './sortable.directive'

@Component({
  template: `
    <table class="table">
      <thead>
        <th></th>
        <th class="d-none d-lg-table-cell" pngxSortable="archive_serial_number">
          ASN
        </th>
        <th class="d-none d-md-table-cell" pngxSortable="correspondent__name">
          Correspondent
        </th>
      </thead>
      <tbody>
        <tr>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </tbody>
    </table>
  `,
})
class TestComponent {}

describe('SortableDirective', () => {
  let fixture: ComponentFixture<TestComponent>
  let directive: SortableDirective
  let des: DebugElement[] // the elements w/ the directive

  beforeEach(() => {
    fixture = TestBed.configureTestingModule({
      declarations: [SortableDirective, TestComponent],
    }).createComponent(TestComponent)

    fixture.detectChanges() // initial binding

    // all elements with an attached SortableDirective
    des = fixture.debugElement.queryAll(By.directive(SortableDirective))

    directive = des[1].injector.get(SortableDirective)
    directive.currentSortField = 'correspondent__name'
  })

  it('should have three 2 sortable elements', () => {
    expect(des.length).toBe(2)
  })

  it('should trigger sort on click', () => {
    const tableCell = des[1].nativeElement as HTMLTableCellElement

    let sortEvent: SortEvent
    directive.sort.subscribe((event) => {
      directive.currentSortReverse = event.reverse
      sortEvent = event
    })

    expect(directive.currentSortReverse).toBeFalsy()

    tableCell.dispatchEvent(new MouseEvent('click'))
    fixture.detectChanges()

    expect(sortEvent).not.toBeNull()
    expect(sortEvent.column).toEqual('correspondent__name')
    expect(sortEvent.reverse).toBeTruthy()

    tableCell.dispatchEvent(new MouseEvent('click'))
    fixture.detectChanges()

    expect(sortEvent.reverse).toBeFalsy()
  })

  it('should change column to sort when clicked', () => {
    const tableCell = des[1].nativeElement as HTMLTableCellElement

    let sortEvent: SortEvent
    directive.sort.subscribe((event) => {
      directive.currentSortReverse = event.reverse
      sortEvent = event
    })

    directive.currentSortField = 'archive_serial_number'

    tableCell.dispatchEvent(new MouseEvent('click'))
    fixture.detectChanges()

    expect(sortEvent.column).toEqual('correspondent__name')
  })
})
