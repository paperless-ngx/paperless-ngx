import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FilterableDropodownComponent } from './filterable-dropdown.component';

describe('FilterableDropodownComponent', () => {
  let component: FilterableDropodownComponent;
  let fixture: ComponentFixture<FilterableDropodownComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ FilterableDropodownComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(FilterableDropodownComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
