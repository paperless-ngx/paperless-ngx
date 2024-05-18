import { TestBed } from '@angular/core/testing'
import { ISODateAdapter } from './ngb-iso-date-adapter'

describe('ISODateAdapter', () => {
  let isoDateAdapter: ISODateAdapter

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ISODateAdapter],
    })
    isoDateAdapter = TestBed.inject(ISODateAdapter)
  })

  it('should parse ISO date to struct', () => {
    let val = isoDateAdapter.fromModel('2023-05-04')
    expect(val.day).toEqual(4)
    expect(val.month).toEqual(5)
    expect(val.year).toEqual(2023)

    val = isoDateAdapter.fromModel(null)
    expect(val).toBeNull()

    val = isoDateAdapter.fromModel('5/4/23')
    expect(val.day).toEqual(4)
    expect(val.month).toEqual(5)
    expect(val.year).toEqual(2023)
  })

  it('should parse struct to ISO date', () => {
    let val = isoDateAdapter.toModel({
      day: 4,
      month: 5,
      year: 2023,
    })
    expect(val).toEqual('2023-05-04')

    val = isoDateAdapter.toModel(null)
    expect(val).toBeNull()
  })
})
