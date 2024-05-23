import { ComponentFixture, TestBed } from '@angular/core/testing'
import { WarehouseComponent } from './warehouse.component'
import { Warehouse } from 'src/app/data/warehouse'
import { By } from '@angular/platform-browser'

const warehouse: Warehouse = {
  id: 1,
  type: 'Warehouse',
  name: 'Warehouse1',
  parent_warehouse: null,

}

describe('WarehouseComponent', () => {
  let component: WarehouseComponent
  let fixture: ComponentFixture<WarehouseComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [WarehouseComponent],
      providers: [],
      imports: [],
    }).compileComponents()

    fixture = TestBed.createComponent(WarehouseComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })


  it('should handle private warehouses', () => {
    expect(
      fixture.debugElement.query(By.css('span')).nativeElement.textContent
    ).toEqual('Private')
  })

  it('should support clickable option', () => {
    component.warehouse = warehouse
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('a.badge'))).toBeNull()
    component.clickable = true
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('a.badge'))).not.toBeNull()
  })
})
