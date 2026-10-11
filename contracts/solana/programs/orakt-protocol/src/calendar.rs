//! Gregorian UTC calendar months, matching the existing site's billing policy.
//! Bounded to 1970..2400; no floating-point arithmetic or 30-day approximation.
const DAY: i64 = 86_400;
fn leap(y: i64) -> bool { y % 4 == 0 && (y % 100 != 0 || y % 400 == 0) }
fn month_days(y: i64, m: i64) -> i64 {
    match m { 2 => if leap(y) {29} else {28}, 4|6|9|11 => 30, _ => 31 }
}
pub fn add_month(timestamp: i64) -> Option<i64> {
    if timestamp < 0 { return None; }
    let time = timestamp % DAY;
    let mut days = timestamp / DAY;
    let mut y = 1970;
    while y < 2400 {
        let n = if leap(y) {366} else {365};
        if days < n {break;} days -= n; y += 1;
    }
    if y >= 2400 { return None; }
    let mut m = 1;
    while days >= month_days(y,m) { days -= month_days(y,m); m += 1; }
    let d = days + 1;
    m += 1;
    if m == 13 { m=1; y+=1; }
    if y >= 2400 { return None; }
    let mut total=0;
    for year in 1970..y { total += if leap(year) {366} else {365}; }
    for month in 1..m { total += month_days(y,month); }
    total += d.min(month_days(y,m))-1;
    total.checked_mul(DAY)?.checked_add(time)
}
pub fn extend(current: i64, now: i64, months: u8) -> Option<i64> {
    if now < 0 || !(1..=12).contains(&months) { return None; }
    let mut end = current.max(now);
    for _ in 0..months { end=add_month(end)?; }
    Some(end)
}
#[cfg(test)]
mod tests {
    use super::*;
    fn utc(y:i64,m:i64,d:i64)->i64 {
        let mut days=0;
        for year in 1970..y {days+=if leap(year){366}else{365};}
        for month in 1..m {days+=month_days(y,month);}
        (days+d-1)*DAY+43_200
    }
    #[test] fn leap_february(){assert_eq!(add_month(utc(2024,1,31)),Some(utc(2024,2,29)));}
    #[test] fn common_february(){assert_eq!(add_month(utc(2025,1,31)),Some(utc(2025,2,28)));}
    #[test] fn century_rule(){assert_eq!(add_month(utc(2100,1,31)),Some(utc(2100,2,28)));}
    #[test] fn rollover(){assert_eq!(add_month(utc(2026,12,31)),Some(utc(2027,1,31)));}
    #[test] fn future_term_preserved(){let t=utc(2027,3,10);assert_eq!(extend(t,utc(2026,10,11),1),Some(utc(2027,4,10)));}
    #[test] fn expired_term_starts_now(){assert_eq!(extend(0,utc(2026,10,11),1),Some(utc(2026,11,11)));}
    #[test] fn bounds(){assert_eq!(extend(0,0,0),None);assert_eq!(extend(0,0,13),None);assert_eq!(add_month(-1),None);assert_eq!(add_month(i64::MAX),None);}
}
